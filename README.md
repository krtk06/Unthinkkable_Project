# Smart Resume Screener

API-first resume parsing and job matching service using FastAPI, MongoDB Atlas, structured LLM output, and local file storage.

## Atlas Setup

1. Create a MongoDB Atlas cluster and database user.
2. Add the development machine's IP address to the Atlas network access list.
3. Copy `.env.example` to `.env` and replace the URI placeholders. Do not commit `.env`.
4. Set `LLM_API_KEY` and `LLM_MODEL` for the OpenAI integration.
5. Run `clamd` as a separate managed service and set `CLAMAV_HOST`/`CLAMAV_PORT`.
6. Install dependencies with `.venv/bin/pip install -e '.[dev]'`.
7. Verify Atlas connectivity with:

```bash
.venv/bin/python -c "from app.config import get_settings; from app.db.client import check_mongo_connection, create_mongo_client; check_mongo_connection(create_mongo_client(get_settings())); print('MongoDB Atlas connection OK')"
```

The application creates the session TTL and candidate lookup indexes when `MongoResumeRepository` is initialized. Atlas Vector Search can be added to the candidate embedding field when semantic retrieval is enabled.

## Development Checks

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/mypy app tests
```

## API Demo

Start the API with `.venv/bin/uvicorn app.main:app --reload` and the Atlas-backed worker in a separate process:

```bash
.venv/bin/python scripts/run_worker.py
```

Then run the safe synthetic upload demo:

```bash
.venv/bin/python scripts/demo_api.py
```

Useful direct calls:

```bash
curl -X POST http://127.0.0.1:8000/v1/sessions \
  -H 'content-type: application/json' \
  -d '{"job_description":"Backend engineer with Python APIs"}'

curl -X POST http://127.0.0.1:8000/v1/sessions/<session_id>/resumes \
  -F 'files=@synthetic-resume.txt;type=text/plain'

curl 'http://127.0.0.1:8000/v1/sessions/<session_id>/matches?min_score=7&limit=25'
```

Uploads are accepted asynchronously at the API boundary, persisted as Atlas jobs, and return batch/job/candidate IDs. Workers claim jobs with leases and retry failed work through the same Atlas cluster.

## Authentication

The API and dashboard require a login. Set `AUTH_SECRET_KEY` in `.env` (a long random string). Users sign up at `http://localhost:3000/signup` with a username, email, and password. To provision an account directly, use:

```bash
.venv/bin/python scripts/create_user.py --username recruiter --email recruiter@example.com
```

Sign in with `POST /v1/auth/login` (`{email, password}`) to receive a bearer token; all `/v1/sessions/*` and `/v1/candidates/*` endpoints require it via `Authorization: Bearer <token>`. The dashboard redirects to `/login` until a valid token is stored.

```bash
# Demo against a running API (after creating a user):
.venv/bin/python scripts/demo_api.py --email recruiter@example.com --password <password>
```

Original resume files use the local filesystem adapter in development. The persistence layer stores session documents with embedded job descriptions, candidates, processing attempts, extraction provenance, embeddings, and match results. OpenAI calls use JSON mode with versioned prompts under `prompts/`; ClamAV scanning fails closed when the service is unavailable or rejects a stream.

## Dashboard

An optional Next.js review dashboard lives in `web/`. It covers session setup with automatic uploads — drop a job description and resumes and they are sent immediately, with no upload buttons. Processing status is polled, and candidates render as ranked cards showing name, highest education, skills, and a 0–10 match score with the evidence-based rubric gauge, plus JSON/CSV export. AI output is labeled as decision support throughout.

Run it against a local API:

```bash
cd web
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
# open http://localhost:3000
```

Checks:

```bash
cd web
npm test            # component/unit tests (vitest)
npm run test:e2e    # Playwright flows on desktop and mobile viewports
npx tsc --noEmit    # type check
```

The e2e suite mocks `/v1/*` responses, so it runs without Atlas, OpenAI, or ClamAV.

## Privacy

Use synthetic or licensed resume fixtures only. Candidate files and parsed PII must not be logged or committed. Configure Atlas encryption, least-privilege users, IP restrictions, and an appropriate retention policy before processing real candidate data.

## Evaluation

Run the extraction and matching evaluation harness (offline, no provider required):

```bash
.venv/bin/python -m tests.evaluation.run --threshold 7
```

The harness measures:
- Field-level precision/recall/F1 for name, email, skills, and experience companies
- Score distance from two-reviewer consensus (mean absolute distance, max distance, within-1-point rate)
- Shortlist false-positive/negative rates at the configured threshold
- Processing latency (mean and p95)

Sample output on the six-resume synthetic manifest:

```json
{
  "extraction": {
    "name": {"precision": 1.0, "recall": 1.0, "f1": 1.0},
    "email": {"precision": 1.0, "recall": 1.0, "f1": 1.0},
    "skills": {"precision": 1.0, "recall": 1.0, "f1": 1.0},
    "experience.companies": {"precision": 1.0, "recall": 1.0, "f1": 1.0}
  },
  "score_agreement": {
    "mean_distance": 0.5,
    "max_distance": 1,
    "within_one_point_rate": 1.0
  },
  "shortlist": {
    "threshold": 7,
    "predicted_shortlist": 3,
    "false_positive_rate": 0.0,
    "consensus_shortlist": 3,
    "false_negative_rate": 0.0
  },
  "latency": {
    "count": 6,
    "mean_seconds": 0.0,
    "p95_seconds": 0.0001
  }
}
```

### Known Limitations

- The evaluation uses a deterministic offline proxy pipeline and six synthetic resumes; it does not exercise real OCR, LLM variance, or non-English text.
- Reviewer consensus is encoded by annotation, not independent human review.
- The production path (OpenAI + ClamAV) must be benchmarked separately against the same metrics by swapping the fake client for `StructuredLLMClient`.
- ClamAV fail-closed behavior means a scanner outage blocks uploads; plan for redundancy.
- Retention cleanup must be scheduled externally (e.g., cron running `scripts/cleanup_retention.py`); TTL removes only session documents, original files are purged by the cleanup script.

## Architecture

```
Client → FastAPI → Local storage + MongoDB → AtlasTaskQueue → ResumeWorker
                                                    ↓
                              OpenAI (JSON mode) ←┘
                                                    ↓
                              Scoring + Embeddings → MongoDB → API → Dashboard
```

- **API layer**: FastAPI with typed request/response models, idempotency keys, consistent error envelopes
- **Queue**: MongoDB-backed `AtlasTaskQueue` with lease-based claims, 3-attempt retries, dead-letter marking
- **Workers**: `ResumeWorker` runs extraction → normalization → scoring; stateless, horizontally scalable
- **Storage**: Local filesystem for originals (dev), session documents in MongoDB with TTL indexes
- **LLM**: OpenAI JSON mode, versioned prompts under `prompts/`, structured output validation with one repair retry
- **Security**: ClamAV fail-closed scanning, PII redaction filter on logs, no PII committed, secrets via env

## Prompts

All prompts are versioned files under `prompts/` and referenced by `prompt_version` in every result:

- `resume_extraction_v1.txt`: extract structured resume fields, no invention, warnings for missing data
- `jd_extraction_v1.txt`: classify requirements as required/preferred, surface ambiguities
- `match_scoring_v1.txt`: 1-10 rubric with evidence citations, strengths/gaps/uncertainty, max 5 evidence items

## Final Verification

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/mypy app tests scripts
```

All checks pass at HEAD `426b46b`.
