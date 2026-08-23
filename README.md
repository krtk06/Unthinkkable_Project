# Smart Resume Screener

API-first resume parsing and job matching service using FastAPI, MongoDB Atlas, structured LLM output, and local file storage.

## Atlas Setup

1. Create a MongoDB Atlas cluster and database user.
2. Add the development machine's IP address to the Atlas network access list.
3. Copy `.env.example` to `.env` and replace the URI placeholders. Do not commit `.env`.
4. Install dependencies with `.venv/bin/pip install -e '.[dev]'`.
5. Verify connectivity with:

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

Start the API with `.venv/bin/uvicorn app.main:app --reload`, then run the safe synthetic upload demo:

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

Uploads are accepted asynchronously at the API boundary and return candidate IDs. Worker execution is currently injectable/local; a production deployment should connect these task functions to its managed queue and Atlas cluster.

Original resume files use the local filesystem adapter in development. The persistence layer stores session documents with embedded job descriptions, candidates, processing attempts, extraction provenance, embeddings, and match results. LLM calls use the provider-neutral interfaces and versioned prompts under `prompts/`.

## Privacy

Use synthetic or licensed resume fixtures only. Candidate files and parsed PII must not be logged or committed. Configure Atlas encryption, least-privilege users, IP restrictions, and an appropriate retention policy before processing real candidate data.
