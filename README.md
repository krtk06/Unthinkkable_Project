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

Original resume files use the local filesystem adapter in development. The persistence layer stores session documents with embedded job descriptions, candidates, processing attempts, extraction provenance, embeddings, and match results. OpenAI calls use JSON mode with versioned prompts under `prompts/`; ClamAV scanning fails closed when the service is unavailable or rejects a stream.

## Dashboard

An optional Next.js review dashboard lives in `web/`. It covers session setup, drag-and-drop resume uploads with client-side validation, processing status polling, the ranked shortlist with threshold/top-N controls and filters, a candidate detail view with parsed fields, score breakdown, evidence quotes, and uncertainty notes, plus JSON/CSV export. Scores render as a 10-segment rubric gauge whose colors match the PRD score bands, and every screen labels AI output as decision support.

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
