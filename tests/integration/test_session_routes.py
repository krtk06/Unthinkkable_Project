from collections.abc import AsyncIterator

import httpx
import mongomock
import pytest
from httpx import ASGITransport

from app.api.dependencies import get_repository
from app.db.mongo_repository import MongoResumeRepository
from app.main import app

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture
def repository() -> MongoResumeRepository:
    return MongoResumeRepository(mongomock.MongoClient()["api_test"])


@pytest.fixture
async def client(repository: MongoResumeRepository) -> AsyncIterator[httpx.AsyncClient]:
    app.dependency_overrides[get_repository] = lambda: repository
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as value:
        yield value
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_create_session_and_upload_resume(client: httpx.AsyncClient) -> None:
    response = await client.post("/v1/sessions", json={"job_description": "Python engineer"})
    assert response.status_code == 201
    session_id = response.json()["session_id"]

    response = await client.post(
        f"/v1/sessions/{session_id}/resumes",
        files={"files": ("resume.txt", b"Ada Python", "text/plain")},
    )

    assert response.status_code == 202
    assert response.json()["accepted"] == 1
    assert response.json()["files"][0]["status"] == "uploaded"


@pytest.mark.anyio
async def test_upload_rejects_unsupported_file_and_missing_session(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/v1/sessions/missing/resumes",
        files={"files": ("resume.exe", b"bad", "application/octet-stream")},
    )
    assert response.status_code == 404

    session_id = (await client.post("/v1/sessions", json={})).json()["session_id"]
    response = await client.post(
        f"/v1/sessions/{session_id}/resumes",
        files={"files": ("resume.exe", b"bad", "application/octet-stream")},
    )
    assert response.status_code == 202
    assert response.json()["rejected"] == 1
    assert response.json()["files"][0]["error"]["code"] == "UNSUPPORTED_FILE"


@pytest.mark.anyio
async def test_status_detail_and_delete_session(client: httpx.AsyncClient) -> None:
    session_id = (await client.post("/v1/sessions", json={})).json()["session_id"]
    upload = await client.post(
        f"/v1/sessions/{session_id}/resumes",
        files={"files": ("resume.txt", b"Ada Python", "text/plain")},
    )
    candidate_id = upload.json()["files"][0]["candidate_id"]

    status = await client.get(f"/v1/sessions/{session_id}/status")
    detail = await client.get(f"/v1/candidates/{candidate_id}")

    assert status.status_code == 200
    assert status.json()["total"] == 1
    assert detail.status_code == 200
    assert detail.json()["candidate_id"] == candidate_id
    assert (await client.delete(f"/v1/sessions/{session_id}")).status_code == 204
    assert (await client.get(f"/v1/sessions/{session_id}/status")).status_code == 404


@pytest.mark.anyio
async def test_matches_support_score_filters_and_cursor_pagination(
    client: httpx.AsyncClient,
    repository: MongoResumeRepository,
) -> None:
    session_id = (await client.post("/v1/sessions", json={})).json()["session_id"]
    candidate = repository.add_resume(
        session_id,
        filename="resume.txt",
        content_type="text/plain",
        size_bytes=4,
        checksum="a" * 64,
        storage_uri="local://a",
    )
    repository.save_match(
        candidate["id"],
        {"candidate_id": candidate["id"], "score": 8},
    )

    response = await client.get(
        f"/v1/sessions/{session_id}/matches", params={"min_score": 7, "limit": 1}
    )

    assert response.status_code == 200
    assert response.json()["matches"][0]["score"] == 8
