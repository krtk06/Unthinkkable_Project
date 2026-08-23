# Smart Resume Screener Implementation Plan

> **For agentic workers:** Implement task-by-task. Keep commits small and meaningful; run the stated verification after each task.

**Goal:** Build an API-first MVP that ingests resumes, extracts structured candidate data, scores candidates against one job description, and optionally displays an evidence-backed shortlist.

**Architecture:** Python 3.12/FastAPI owns the REST contract. A worker pipeline performs file extraction, optional OCR, schema-constrained LLM extraction, embeddings, and LLM scoring. MongoDB stores session documents with embedded candidate state, scores, audit attempts, and TTL retention; private object storage holds original files. An optional Next.js dashboard consumes only the API.

**Tech Stack:** Python, FastAPI, Pydantic v2, PyMongo, MongoDB, local queue adapter (replaceable with Redis/Celery), pypdf, python-docx, OCR adapter, provider-agnostic LLM client, pytest, and optional Next.js/TypeScript.

## Global Constraints

- Enforce 10 MB/file, 100 files/batch, 500 PDF pages, and 20,000 extracted characters.
- Preserve missing values as `null` or empty arrays; never invent resume facts.
- Score on a 1-10 rubric and cite candidate evidence for material claims.
- Do not use protected characteristics or inferred demographic traits.
- Store prompt version, model, processing status, and timestamps with each result.
- Use `202 Accepted` for asynchronous batch processing and per-file failure isolation.
- Default retention is 30 days and must be configurable.
- MVP language is English unless a stakeholder changes the decision.

## Target Repository Layout

Create this structure before feature work:

```text
app/
  main.py                 # FastAPI application and router registration
  config.py               # environment-backed settings
  api/                    # request/response models and route handlers
  domain/                 # canonical schemas and scoring types
  db/                     # MongoDB client, document repositories, indexes
  ingestion/              # validation, extraction, OCR, object storage
  llm/                    # provider interface, prompts, JSON validation
  matching/               # embeddings, rubric scoring, ranking/filtering
  workers/                # queue tasks and state transitions
tests/
  fixtures/resumes/       # safe synthetic or licensed samples
  unit/
  integration/
prompts/
  resume_extraction_v1.txt
  jd_extraction_v1.txt
  match_scoring_v1.txt
web/                      # optional dashboard
README.md
.env.example
```

Each task below is complete only when its listed implementation, tests, and verification command have passed. Convert each task's action bullets to checked items as work progresses.

## Phase 0: Repository and Contracts

**Outcome:** A runnable service with documented contracts and no provider dependency in route code.

### Task 0.1: Initialize the service

- Create `pyproject.toml` with Python 3.12, FastAPI, Pydantic, PyMongo, pytest, ruff, and mypy.
- Create `app/main.py` with `/health` returning `{ "status": "ok" }`.
- Create `app/config.py` for `MONGO_URI`, `MONGO_DATABASE`, `OBJECT_STORAGE_BUCKET`, `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `MAX_FILE_BYTES`, and `RETENTION_DAYS`.
- Create `.env.example` without secrets and document MongoDB Atlas setup; no Docker files are required.
- Verify with `pytest`, `ruff check .`, and `curl http://localhost:8000/health`.
- Commit: `chore: initialize resume screener service`.

### Task 0.2: Define canonical schemas first

- Implement `app/domain/resume.py` with Pydantic models matching the `ExtractedResume` schema in `PRD.md`.
- Implement `app/domain/job.py` and `app/domain/match.py` for normalized requirements and match output.
- Add tests for valid data, missing sections, invalid score bounds, invalid dates, and extra fields.
- Generate or expose JSON Schema from Pydantic and compare the checked-in contract to API examples.
- Verify with `pytest tests/unit/test_domain_schemas.py -v`.
- Commit: `feat: add canonical resume and match schemas`.

## Phase 1: Resume Ingestion and Parsing

**Outcome:** A file can be validated, safely stored, converted to text, and represented as a schema-valid parsed resume.

### Task 1.1: Implement file validation and storage

- Create `app/ingestion/validation.py` with `validate_upload(filename, content_type, size_bytes) -> None` and typed errors for unsupported type, size, and empty file.
- Create `app/ingestion/storage.py` with `put_original(file_bytes, checksum, content_type) -> str`, `get_original(uri)`, and `delete_original(uri)`.
- Use checksum-based object keys and never log file bytes or PII.
- Test PDF, DOCX, text acceptance; executable/incorrect MIME rejection; 10 MB boundary; duplicate checksum; and private object metadata.
- Verify with `pytest tests/unit/test_validation.py tests/unit/test_storage.py -v`.
- Commit: `feat: validate and persist resume uploads`.

### Task 1.2: Implement text extraction and OCR fallback

- Create `app/ingestion/text_extract.py` with `extract_text(file_bytes, content_type) -> ExtractionResult(text, page_count, ocr_used, warnings)`.
- Use pypdf for text PDFs, python-docx for DOCX, UTF-8 decoding for text, and an injectable `OCRClient` when extracted text density is below the configured threshold.
- Raise `UNREADABLE_FILE` for corrupt/encrypted files and return `OCR_LOW_CONFIDENCE` warnings instead of fabricated text.
- Add synthetic fixtures for a normal PDF, DOCX, scanned-image stub, malformed file, and missing-text document.
- Verify with `pytest tests/unit/test_text_extract.py -v`.
- Commit: `feat: extract resume text with OCR fallback`.

### Task 1.3: Add MongoDB document repository and processing state

- Create `app/db/mongo_repository.py` with one session document containing job description, candidates, processing attempts, embeddings, and matches.
- Persist raw file URI/checksum, extracted text metadata, parsed JSON, status, error code, model/prompt versions, and timestamps.
- Add repository methods: `create_session`, `add_resume`, `update_stage`, `save_extraction`, `save_match`, `delete_session`.
- Enforce session-scoped checksum uniqueness, atomic positional updates, candidate IDs, and a TTL index on `expires_at`.
- Verify with `mongomock` unit tests and a documented Atlas connectivity smoke test.
- Commit: `feat: persist screening sessions and processing state`.

### Task 1.4: Implement extraction prompt adapter

- Store the exact resume prompt in `prompts/resume_extraction_v1.txt`.
- Create `app/llm/client.py` with protocol methods `extract_resume(text: str) -> ExtractedResume`, `extract_job(text: str) -> JobRequirements`, and `score_match(requirements, resume, embedding_context) -> MatchResult`.
- Create `app/llm/validation.py` to parse JSON, validate Pydantic schema, check evidence references, and return typed validation errors.
- Add a fake client for tests; do not call a real provider in unit tests.
- Verify malformed JSON, missing fields, invented values, and one repair retry behavior.
- Commit: `feat: add provider-agnostic structured LLM client`.

## Phase 2: JD Normalization and Matching

**Outcome:** A session produces deterministic, explainable ranked matches.

### Task 2.1: Normalize job descriptions

- Store the exact JD input and normalized `JobRequirements` separately.
- Implement `app/matching/job_requirements.py` with required/preferred classification, ambiguity collection, and user-confirmable output.
- Use `prompts/jd_extraction_v1.txt`; enforce the rule that unlabeled requirements become preferred with an ambiguity note.
- Test explicit “must have,” “nice to have,” broad requirements, empty descriptions, and structured input.
- Verify with `pytest tests/unit/test_job_requirements.py -v`.
- Commit: `feat: normalize job description requirements`.

### Task 2.2: Add embeddings behind an interface

- Create `app/matching/embeddings.py` with `EmbeddingClient.embed(text: str) -> list[float]` and `build_candidate_text(resume) -> str`.
- Store embedding model/version and vector in MongoDB or Atlas Vector Search when enabled; make the client no-op configurable for small batches.
- Use embeddings only as context/retrieval support, never as the sole explanation or final decision.
- Test deterministic fake vectors, cache-key construction from content/model/version, and disabled-provider behavior.
- Verify with `pytest tests/unit/test_embeddings.py -v`.
- Commit: `feat: add optional semantic embedding retrieval`.

### Task 2.3: Implement rubric scoring and validation

- Store `prompts/match_scoring_v1.txt` exactly as specified in `PRD.md`.
- Implement `app/matching/scoring.py` with `score_candidate(requirements, resume, embedding_context) -> MatchResult`.
- Validate integer score 1-10, coverage 0-1, max five evidence items, source paths that exist, and quotes that match supplied evidence.
- Retry transient provider errors with exponential backoff, maximum three attempts; retry schema repair once; persist terminal errors.
- Test the PRD example: Python/REST required and Kubernetes preferred must yield a valid score with a Kubernetes-not-found gap when using the fake client.
- Verify with `pytest tests/unit/test_scoring.py -v`.
- Commit: `feat: score candidates with evidence-backed rubric`.

### Task 2.4: Implement shortlist ranking and filters

- Create `app/matching/ranking.py` with `rank_matches(matches, threshold=None, top_n=None, filters=None) -> list[MatchResult]`.
- Apply score descending, required coverage descending, candidate ID ascending as the deterministic tie-break.
- Test threshold mode, top-N mode, score/coverage/location filters, pagination, and empty results.
- Verify with `pytest tests/unit/test_ranking.py -v`.
- Commit: `feat: add shortlist ranking and filtering`.

### Task 2.5: Add asynchronous workers

- Create `app/workers/tasks.py` with idempotent tasks `process_resume(resume_id)` and `score_candidate(candidate_id)`.
- Define stage transitions and ensure a failed resume does not fail sibling batch jobs.
- Add request/job IDs to structured logs and metrics for duration, retry count, provider errors, OCR use, and token/cost estimates.
- Verify a batch of 10 fake resumes completes with mixed success/failure and can be retried safely.
- Commit: `feat: process resume batches asynchronously`.

## Phase 3: REST API

**Outcome:** Developers can run the complete workflow without the dashboard.

### Task 3.1: Create session and upload routes

- Implement `POST /v1/sessions`, `POST /v1/sessions/{id}/job-description`, and `POST /v1/sessions/{id}/resumes` in `app/api/routes/sessions.py`.
- Use multipart upload, request size limits, idempotency keys, and `202` responses containing session/job/file IDs.
- Return the exact error shape from the PRD and never include raw LLM output in normal errors.
- Add route tests for one upload, bulk upload, unsupported files, duplicate checksums, and missing session.
- Verify with `pytest tests/integration/test_session_routes.py -v`.
- Commit: `feat: expose session and resume upload API`.

### Task 3.2: Create status, match, and detail routes

- Implement `GET /v1/sessions/{id}/status`, `GET /v1/sessions/{id}/matches`, `GET /v1/candidates/{id}`, `DELETE /v1/sessions/{id}`, and `/health` readiness checks.
- Support cursor pagination, threshold/top-N, filtering, and stable ordering.
- Add OpenAPI examples for parsed candidate data and match evidence.
- Verify with integration tests covering processing progress, partial failures, deletion, and authorization boundary hooks.
- Commit: `feat: expose match results and candidate detail API`.

### Task 3.3: Add README and runnable demo script

- Document Atlas setup, environment variables, provider configuration, API curl examples, prompt versions, scoring caveats, retention, and test commands in `README.md`.
- Add a safe synthetic sample session script that demonstrates upload through ranked output without committing secrets or real candidate PII.
- Verify a new developer can run the demo from a clean checkout using the documented commands.
- Commit: `docs: document architecture prompts and API workflow`.

## Phase 4: Optional Dashboard

**Outcome:** A reviewer can complete the core workflow visually and inspect evidence quickly.

### Task 4.1: Scaffold dashboard and session setup

- Create `web/` with Next.js, TypeScript, and typed API client generated from OpenAPI.
- Build a session form for JD text/options and a drag-and-drop resume uploader showing file validation errors.
- Add accessible labels, keyboard navigation, responsive layout, and an explicit AI decision-support disclaimer.
- Test form validation and upload states with component tests.
- Commit: `feat: add dashboard session setup and uploads`.

### Task 4.2: Build ranked list and detail view

- Implement status polling, candidate table, score/coverage columns, threshold/top-N controls, filters, stable sort indicators, and empty/error states.
- Implement candidate detail tabs for parsed fields, score breakdown, strengths, gaps, evidence quotes, uncertainty, and raw-file metadata.
- Add JSON/CSV export through API or a client-side download of the paginated result.
- Verify mobile and desktop flows with Playwright: upload, wait for completion, filter, open detail, inspect evidence, export.
- Commit: `feat: add shortlist review dashboard`.

## Phase 5: Evaluation, Security, and Demo

**Outcome:** The project is demonstrable, measurable, and safe enough for an MVP review.

### Task 5.1: Build the evaluation harness

- Create `tests/evaluation/` with an annotated manifest containing resume ID, expected fields, expected requirements, and two-reviewer score consensus.
- Implement field-level precision/recall/F1, score distance, shortlist false-positive/negative rate, and latency reports.
- Use synthetic or licensed data only; document dataset limitations and do not commit real PII.
- Verify the report includes the PRD targets and a reproducible command such as `python -m tests.evaluation.run`.
- Commit: `test: add extraction and matching evaluation harness`.

### Task 5.2: Add retention, privacy, and operational hardening

- Implement scheduled deletion for records older than configured retention and explicit session deletion.
- Redact email, phone, resume text, and raw model output from logs; add secret scanning and dependency audit to CI.
- Add provider timeout, retry, dead-letter visibility, readiness checks, and metrics dashboards or a documented local substitute.
- Verify deletion removes object storage and database data, retries do not duplicate records, and logs contain no sample PII.
- Commit: `feat: enforce retention and operational safeguards`.

### Task 5.3: Finalize repository and demo

- Run `pytest`, `ruff check .`, type checks, Atlas index checks, and Playwright tests when the dashboard is included.
- Review every prompt for schema compliance, no-invention language, evidence citation, and version metadata.
- Record a 2-3 minute demo: create session, upload several resumes, show progress/partial failure, inspect ranked score and evidence, apply filter, and delete the session.
- Update README with measured metrics, known limitations, architecture diagram text, prompts, and demo link.
- Commit: `docs: finalize MVP evaluation and demo materials`.

## Definition of Done

- All API contracts in `PRD.md` are implemented or explicitly marked optional dashboard functionality.
- Unit and integration tests cover valid inputs, malformed files, missing fields, LLM validation/retries, ranking, and deletion.
- No score is returned without structured output validation and evidence/uncertainty fields.
- Extraction and matching metrics are measured on a documented sample set.
- README, prompt files, meaningful commit history, and 2-3 minute demo are present.
- `git status` is clean except for intentionally untracked local environment files ignored by `.gitignore`.

## Decision Record

- **Python over Node.js/Java:** Python has the best document, NLP, embedding, and LLM tooling for this workload; FastAPI supplies adequate I/O performance.
- **MongoDB over PostgreSQL:** resume extraction and match payloads are document-shaped and change with prompt versions; embedded session documents, atomic updates, and TTL indexes reduce persistence complexity. Atlas Vector Search is the production vector-search option.
- **Embeddings plus constrained LLM:** embeddings improve semantic retrieval and cost; the LLM supplies rubric reasoning and evidence. Neither is trusted without validation.
- **Async queue:** uploads and OCR/LLM calls exceed safe request durations and need per-file retries and partial batch success.
- **Dashboard optional:** the API is the smallest independently useful MVP; the dashboard is a review accelerator and demo layer, not a prerequisite for backend correctness.
