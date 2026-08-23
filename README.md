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

Original resume files use the local filesystem adapter in development. The persistence layer stores session documents with embedded job descriptions, candidates, processing attempts, extraction provenance, embeddings, and match results. LLM calls use the provider-neutral interfaces and versioned prompts under `prompts/`.

## Privacy

Use synthetic or licensed resume fixtures only. Candidate files and parsed PII must not be logged or committed. Configure Atlas encryption, least-privilege users, IP restrictions, and an appropriate retention policy before processing real candidate data.
