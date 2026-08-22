# Smart Resume Screener

## 1. Overview & Problem Statement

Smart Resume Screener replaces the manual first-pass process in which a recruiter opens resumes one at a time, searches for keywords, copies facts into a spreadsheet, and makes an inconsistent shortlist. It accepts resumes and a job description, extracts normalized candidate data, evaluates evidence against the role, and returns ranked candidates with an explainable score.

Target users are recruiters, hiring managers, HR teams, and small businesses or startups that need lightweight screening without buying or configuring a full ATS.

The core value proposition is faster, more consistent, evidence-based screening. Keyword ATS filters miss synonyms, equivalent experience, transferable skills, and context (for example, “built REST services” versus “API development”), while an LLM can compare meaning and seniority in context. LLM output must remain constrained by an explicit rubric and cited resume evidence; it is decision support, not an autonomous hiring decision.

## 2. Goals & Success Metrics

### Goals

- Extract reliable structured data from PDF, DOCX, and text resumes.
- Produce a 1-10 match score that is repeatable, calibrated to a rubric, and supported by evidence.
- Reduce screening time while preserving recruiter control and auditability.
- Expose a clean REST API and an optional, scannable dashboard.

### Non-goals

- This is not a full ATS, applicant tracking workflow, interview scheduler, or offer system.
- No candidate-facing portal, candidate messaging, assessments, or automated rejection emails.
- No autonomous hiring decision; a human owns the shortlist decision.
- No multi-stage bulk hiring pipeline, background checks, reference checks, or identity verification.
- No guarantee of legal compliance in every jurisdiction; the deployment owner remains responsible for employment-law review.

### Success criteria

| Metric | MVP target | Measurement |
|---|---:|---|
| Required-field extraction F1 | >= 90% on an annotated 100-resume set | Field-level precision/recall; contact fields excluded from semantic scoring if absent |
| Experience/skill extraction F1 | >= 85% | Human-labeled skills and employment records |
| Score agreement | >= 80% of results within 1 rubric point of a two-reviewer consensus | Held-out resume/JD benchmark |
| Shortlist false-positive rate | <= 15% at configured threshold | Reviewer labels on benchmark set |
| Shortlist false-negative rate | <= 15% for clearly qualified candidates | Reviewer labels on benchmark set |
| Processing latency | p95 <= 30 seconds per text-based resume; p95 <= 60 seconds with OCR | Upload through completed score |
| API availability | >= 99.5% monthly for synchronous API | Monitoring |
| Screening time saved | >= 60% versus baseline | Timed usability study with recruiters |

## 3. User Personas & Use Cases

### Personas

- **Maya, recruiter:** Screens 50 resumes for one role and needs an initial ranked list without manually opening every file.
- **Devon, hiring manager:** Wants to inspect the top candidates and understand exactly why each appears suitable or unsuitable.
- **Rina, HR operations:** Uploads a small batch, needs processing status, downloadable JSON/CSV, retention controls, and predictable failures.

### User stories

- As a recruiter, I want to upload one or many resumes against a job description, so that I can create a ranked review queue.
- As a recruiter, I want to filter by score, required-skill coverage, years of experience, and education, so that I can focus on relevant candidates.
- As a hiring manager, I want bullet-point evidence for every score, so that I can validate the recommendation quickly.
- As a hiring manager, I want missing requirements called out separately from weak evidence, so that I do not confuse “not found” with “not qualified.”
- As HR operations, I want per-file status and error messages, so that one malformed resume does not fail the entire batch.
- As an administrator, I want retention and deletion controls, so that candidate data is not stored longer than necessary.

## 4. Functional Requirements

### a) Resume Ingestion

- Accept PDF, DOCX, and UTF-8 plain text through `multipart/form-data` and a bulk upload endpoint.
- MVP limits: 10 MB per file, 100 files per batch, 500 pages per PDF, and 20,000 characters after extraction. Reject larger files with a machine-readable error.
- Validate MIME type and extension, reject encrypted/password-protected files unless supported by a future release, and malware-scan uploads before processing.
- Store an immutable file identifier and checksum. Deduplicate identical files within a workspace/session.
- Return `202 Accepted` for batch work with a job ID. A failed file must have status `failed`, an error code, and a human-readable message while other files continue.

### b) Data Extraction / Parsing

Extract name, contact information, location, skills, work experience (company, role, dates, duration, description), education, certifications, languages, and source-quality warnings. Preserve evidence spans or source snippets where feasible.

The canonical output is:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ExtractedResume",
  "type": "object",
  "required": ["schema_version", "candidate", "skills", "experience", "education", "certifications", "warnings"],
  "properties": {
    "schema_version": {"type": "string", "const": "1.0"},
    "candidate": {
      "type": "object",
      "required": ["name", "contact", "location"],
      "properties": {
        "name": {"type": ["string", "null"]},
        "contact": {
          "type": "object",
          "required": ["email", "phone", "url"],
          "properties": {
            "email": {"type": ["string", "null"], "format": "email"},
            "phone": {"type": ["string", "null"]},
            "url": {"type": ["string", "null"], "format": "uri"}
          },
          "additionalProperties": false
        },
        "location": {"type": ["string", "null"]}
      },
      "additionalProperties": false
    },
    "skills": {"type": "array", "items": {"type": "string"}},
    "experience": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["company", "role", "start_date", "end_date", "duration_months", "description"],
        "properties": {
          "company": {"type": ["string", "null"]},
          "role": {"type": ["string", "null"]},
          "start_date": {"type": ["string", "null"], "pattern": "^\\d{4}(-\\d{2})?$"},
          "end_date": {"type": ["string", "null"]},
          "duration_months": {"type": ["integer", "null"], "minimum": 0},
          "description": {"type": "string"},
          "evidence": {"type": "array", "items": {"type": "string"}}
        },
        "additionalProperties": false
      }
    },
    "education": {"type": "array", "items": {"type": "object", "required": ["institution", "degree", "field", "graduation_date"], "properties": {"institution": {"type": ["string", "null"]}, "degree": {"type": ["string", "null"]}, "field": {"type": ["string", "null"]}, "graduation_date": {"type": ["string", "null"]}}, "additionalProperties": false}},
    "certifications": {"type": "array", "items": {"type": "object", "required": ["name", "issuer", "date"], "properties": {"name": {"type": "string"}, "issuer": {"type": ["string", "null"]}, "date": {"type": ["string", "null"]}}, "additionalProperties": false}},
    "languages": {"type": "array", "items": {"type": "string"}},
    "warnings": {"type": "array", "items": {"type": "string"}}
  },
  "additionalProperties": false
}
```

Parser stages are text extraction, cleanup/section detection, LLM structured extraction, schema validation, normalization (dates, duplicate skills), and confidence/warning generation. Never invent missing values: use `null`, empty arrays, or a warning.

### c) Job Description Input

Accept free text, structured JSON, or a text-bearing file. Normalize to title, summary, required skills, preferred skills, responsibilities, minimum experience, education, certifications, location/work mode, and constraints. Explicit labels such as “must have” map to required requirements; unlabeled requirements default to preferred until reviewed by the user. The API returns the normalized JD for confirmation before scoring.

### d) LLM-Based Matching & Scoring

Recommended methodology: use embeddings for candidate/JD retrieval and semantic similarity, then use one constrained LLM scoring call for requirement-by-requirement reasoning. Embeddings alone are not sufficiently explainable; pure LLM scoring is slower, less stable, and harder to calibrate. For an MVP with small batches, scoring can run without a vector index, while retaining the interface for embeddings.

Score each candidate from 1-10 using this rubric:

| Score | Meaning |
|---:|---|
| 1-2 | No credible evidence; major required requirements absent |
| 3-4 | Limited alignment; several required gaps |
| 5-6 | Partial alignment; some required evidence, meaningful gaps or uncertainty |
| 7-8 | Strong alignment; most required requirements evidenced and preferred items useful |
| 9 | Very strong alignment; all material required requirements evidenced with relevant depth |
| 10 | Exceptional alignment; requirements and context substantially exceed the role bar |

Output must include overall score, required coverage, preferred coverage, strengths, gaps, uncertainty, and 2-5 evidence bullets. Each evidence bullet cites a normalized field and a verbatim or near-verbatim resume excerpt. “Not found” is distinct from “does not have.” The system must not use protected characteristics or inferred demographic traits in scoring.

### e) Shortlisting & Ranking

Support both `threshold` and `top_n` modes. Default threshold is 7, configurable per request. Rank by score descending, then required coverage descending, then deterministic candidate ID. Provide filters for score range, required-skill status, years/months of experience, location/work mode, and processing status.

### f) Output & Display

Core API response:

```json
{
  "candidate_id": "cand_123",
  "score": 8,
  "required_coverage": 0.9,
  "preferred_coverage": 0.67,
  "strengths": ["Python APIs", "Four years of production backend work"],
  "gaps": ["Kubernetes experience not found"],
  "evidence": [{"claim": "Python API experience", "source": "experience[0].description", "quote": "Built and operated Python REST services"}],
  "uncertainty": ["Employment dates are month-only"],
  "model": {"provider": "configured-provider", "model": "configured-model", "prompt_version": "match-v1"}
}
```

Optional dashboard: upload/session setup, processing progress, ranked candidate table, score/coverage columns, filter and sort controls, candidate detail with evidence and raw/parsed tabs, and export JSON/CSV. It must visibly label AI-generated recommendations and preserve human review.

### g) Data Storage

Persist session/JD metadata, raw resume in private object storage, parsed JSON, normalized requirements, scores, justifications, model/prompt versions, processing status, timestamps, and audit events. MongoDB stores session documents with embedded candidate state and TTL retention; object storage stores originals. Default retention is 30 days, configurable to 0-365 days; deletion removes object and database records, subject to an auditable deletion event. Encrypt in transit and at rest, minimize PII in logs, restrict access by workspace, and support export/deletion requests.

## 5. Non-Functional Requirements

- **Performance:** p95 <= 10 seconds text extraction plus parse and <= 30 seconds full score; OCR path p95 <= 60 seconds. Batch jobs must stream status rather than hold an HTTP request open.
- **Scalability:** process at least 10 concurrent resumes and 100-resume batches through a queue; worker concurrency and provider rate limits are configurable.
- **Security/privacy:** TLS, encrypted object storage/database, secrets in environment/secret manager, least-privilege service accounts, malware scanning, redacted logs, tenant/session authorization, and no training use by the LLM provider where contractually available. Conduct DPIA/legal review for GDPR/EEA use, provide deletion/export, define controller/processor roles, and do not make protected-trait inferences.
- **Reliability:** typed error codes, per-stage status, timeouts, exponential backoff for transient LLM/storage failures, maximum three retries with jitter, dead-letter visibility, idempotency keys, and graceful partial batch completion.
- **Cost:** target an initial blended cost below $0.10 per text resume and below $0.20 with OCR, subject to provider pricing. Truncate irrelevant text only after extraction, cache by file/JD/model/prompt hash, use embeddings for retrieval, batch where provider supports it, and avoid repeated scoring.

## 6. Technical Architecture

### High-level flow

`Client -> API -> object storage + MongoDB -> queue -> extraction worker -> parser/OCR -> structured JSON -> embedding worker -> scoring worker/LLM -> MongoDB -> API/dashboard`.

The API creates an idempotent processing session. Workers update state transitions (`uploaded`, `text_extracted`, `parsed`, `scored`, `failed`) and emit structured logs/metrics. The dashboard polls or subscribes to status via a future SSE endpoint.

### Backend recommendation

Use Python 3.12, FastAPI, Pydantic v2, PyMongo, a queue such as Celery/RQ/managed queues, `pypdf`, `python-docx`, and an OCR adapter (Tesseract or managed OCR). Python is recommended because its NLP, embedding, document parsing, evaluation, and LLM ecosystem is strongest. Node.js offers a single-language full-stack and good I/O performance, but adds more ecosystem choices for document/NLP work. Java is strong for enterprise governance and throughput, but is slower to prototype for this NLP-heavy MVP.

### Database

Use MongoDB for the MVP because candidate resumes, extraction payloads, scores, and justifications are naturally document-shaped and evolve as prompts improve. Store one screening session document with embedded job description and candidate records; use atomic positional updates and TTL indexes for retention. Use MongoDB Atlas Vector Search for production semantic retrieval or a compatible local representation during development. Object storage remains the preferred location for original files.

### LLM integration

Use a provider abstraction (`LLMClient.extract`, `LLMClient.extract_job`, `LLMClient.score`) so the provider/model is configurable. Prefer a provider with JSON mode or schema-constrained structured outputs. Use separate calls for resume extraction, JD extraction, and matching; this improves validation, retries, observability, and prompt versioning. Use low temperature (0-0.2), deterministic normalization, and Pydantic/JSON Schema validation with one repair retry. Never let free-form model output directly drive ranking.

### Frontend

If included, use Next.js/React, TypeScript, and a small component system. Keep the dashboard thin: API owns processing and scoring; the UI owns session setup, status, filters, and evidence presentation.

### REST API

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/v1/sessions` | Create a screening session with JD text/options |
| POST | `/v1/sessions/{session_id}/resumes` | Upload one or many resumes; returns job/file IDs |
| POST | `/v1/sessions/{session_id}/job-description` | Create or replace JD input |
| GET | `/v1/sessions/{session_id}/status` | Processing counts and per-file status |
| GET | `/v1/sessions/{session_id}/matches` | Ranked, filtered, paginated matches |
| GET | `/v1/candidates/{candidate_id}` | Parsed data, score, evidence, and file metadata |
| DELETE | `/v1/sessions/{session_id}` | Delete session and retained candidate data |
| GET | `/health` | Liveness/readiness |

Use OpenAPI, request IDs, pagination cursors, idempotency keys, and consistent errors: `{ "error": { "code": "UNSUPPORTED_FILE", "message": "...", "details": {} } }`.

## 7. LLM Prompt Design Specification

All prompts are versioned files, use explicit delimiters, prohibit invention, and require JSON schema validation.

### a) Resume extraction prompt

**Input:** raw extracted resume text and `ExtractedResume` schema.

```text
SYSTEM: You extract facts from resumes. Return only JSON matching schema ExtractedResume v1.0.
Do not infer facts. If a value is absent or ambiguous, use null and add a warning. Preserve dates as YYYY or YYYY-MM where possible. Ignore protected characteristics and do not score the candidate.

USER:
<resume_text>
{resume_text}
</resume_text>
Return the schema-conforming JSON object now.
```

### b) JD requirement extraction prompt

**Output schema:** `{ "title": string|null, "required": [{"name": string, "type": "skill|experience|education|certification|constraint", "minimum": string|null}], "preferred": [...], "responsibilities": [string], "ambiguities": [string] }`.

```text
SYSTEM: Convert a job description into explicit requirements. Do not add requirements not supported by the text. Phrases such as must, required, minimum, or mandatory are required; phrases such as preferred, nice to have, or bonus are preferred. If classification is ambiguous, place it in preferred and explain the ambiguity.
USER: <job_description>{jd_text}</job_description>
Return only the specified JSON.
```

### c) Match scoring prompt

**Output schema:** `{ "score": integer, "required_coverage": number, "preferred_coverage": number, "strengths": [string], "gaps": [string], "evidence": [{"claim": string, "source": string, "quote": string}], "uncertainty": [string] }` with score 1-10, coverage 0-1, and max five evidence items.

```text
SYSTEM: You are a screening decision-support evaluator. Score only against the supplied requirements and resume evidence. Do not infer protected traits, personality, intent, or facts not present. “Not found” is not proof of absence. Required requirements weigh more than preferred requirements. Return only valid JSON matching the schema.
RUBRIC: 1-2 no credible evidence; 3-4 limited; 5-6 partial; 7-8 strong; 9 very strong; 10 exceptional.
USER:
<requirements>{requirements_json}</requirements>
<candidate>{extracted_resume_json}</candidate>
<similarity_context>{embedding_context}</similarity_context>
For every material strength or gap, cite a source field and a short exact quote. Return JSON.
```

### End-to-end scoring example

**Input:** requirements require Python and REST APIs, prefer Kubernetes; candidate has `"skills":["Python"]` and experience description `"Built and operated Python REST services for four years."` with no Kubernetes evidence.

**Output:**

```json
{"score":8,"required_coverage":1.0,"preferred_coverage":0.0,"strengths":["Four years of Python REST-service experience"],"gaps":["Kubernetes experience not found"],"evidence":[{"claim":"Python REST APIs","source":"experience[0].description","quote":"Built and operated Python REST services for four years."}],"uncertainty":[]}
```

Set temperature to 0-0.2. Include 3-5 few-shot examples during calibration, not arbitrary examples in production. Validate schema, numeric bounds, evidence-source existence, and quote substring similarity. Retry once with validation errors; otherwise mark the score failed for human review. Store prompt and model versions with every result.

## 8. Edge Cases & Error Handling

- **Corrupted PDFs:** detect parser failure, attempt a second parser, then mark `UNREADABLE_FILE`; do not send binary garbage to the LLM.
- **Scanned/image PDFs:** detect low extracted text density, run OCR, record `ocr_used`, confidence, and page failures. If confidence is too low, return partial extraction plus a review warning.
- **Non-English resumes:** MVP assumes English. Detect language and return `UNSUPPORTED_LANGUAGE` or route supported languages through a translation/extraction adapter without silently translating evidence; stakeholder choice is required.
- **Missing sections:** use null/empty arrays and warnings; missing education must not be treated as a negative unless the JD explicitly requires it.
- **Malformed LLM output:** schema validate, attempt one repair call, then fail the stage with raw output stored only in restricted diagnostics.
- **Ambiguous/broad JD:** surface `ambiguities`, request user confirmation, and down-weight uncertain requirements rather than pretending precision.
- **LLM timeout/rate limit:** retry transient failures with backoff; after three attempts mark the candidate retryable/failed and leave other candidates unaffected.
- **Duplicate resume:** checksum and session-scoped deduplication prevent double ranking.

## 9. Milestones & Deliverables

| Phase | Scope | Effort |
|---|---|---:|
| 1. Parsing pipeline | Project setup, ingestion, PDF/DOCX/text extraction, OCR adapter, schema validation, persistence, benchmark fixtures | 4-5 days |
| 2. LLM scoring | JD extraction, resume extraction, prompt versions, embeddings interface, scoring rubric, retries, evaluation harness, REST matches | 4-5 days |
| 3. Dashboard | Session creation, uploads, progress, ranked list, filters, candidate detail/evidence, export | 3-4 days |
| 4. Polish/demo | Security review, retention/delete, observability, cost controls, README, sample data, integration tests, 2-3 minute demo video | 2-3 days |

Deliverables: GitHub repository with meaningful commits by vertical slice; README covering setup, architecture, environment variables, API use, prompts, evaluation, and limitations; automated tests; sample benchmark results; and a 2-3 minute demo showing upload, processing, ranked output, and evidence drill-down.

## 10. Evaluation Criteria Alignment

| Evaluation focus | Feature/deliverable | What good looks like |
|---|---|---|
| Code quality & structure | Parser, LLM, storage, API, and UI modules | Clear separation of concerns, typed interfaces, small testable units, meaningful commits, no provider logic scattered through routes |
| Data extraction accuracy | Canonical schema, normalization, fixture set, metrics | Extraction validated against annotated resumes; missing data represented honestly; malformed inputs covered |
| LLM prompt quality | Versioned prompts, schemas, examples, retry validation | Explicit constraints, evidence citations, stable rubric, no-invention rule, reproducible model/prompt metadata |
| Output clarity | API contract and dashboard | Scannable ranking, coverage and score breakdown, specific evidence and gaps, visible uncertainty, human-in-the-loop labeling |
| Engineering completeness | README, tests, demo, retention/security controls | A reviewer can run the project, understand tradeoffs, reproduce a sample, and see failures handled gracefully |

## 11. Open Questions / Assumptions

### Assumptions used for this PRD

- MVP targets English resumes and English job descriptions.
- One job description is active per screening session.
- MVP supports one workspace or trusted deployment; production multi-tenancy/auth is an extension unless required.
- A managed LLM API is acceptable; no self-hosted model requirement.
- Human reviewers make final decisions and can override or ignore scores.
- Dashboard is optional for the API MVP but included in the recommended delivery plan.
- Initial batch size is 100 resumes and files are at most 10 MB each.

### Stakeholder decisions required

- Which LLM provider/model and maximum per-resume budget should be used?
- Is the dashboard mandatory, or is a polished API sufficient for the first release?
- Should non-English resumes be rejected, translated, or supported natively?
- Is authentication, multi-tenancy, SSO, or audit export required for the target deployment?
- What retention period and deletion SLA are required by the organization and applicable jurisdictions?
- Which benchmark resumes/JDs and reviewer panel will establish extraction and shortlist ground truth?
- Should OCR use a managed service or a self-hosted Tesseract adapter?
