from collections.abc import AsyncIterator

import httpx
import mongomock
import pytest
from httpx import ASGITransport

from app.api.dependencies import (
    get_llm_client,
    get_malware_scanner,
    get_queue,
    get_repository,
    get_user_repository,
)
from app.config import Settings, get_settings
from app.db.mongo_repository import MongoResumeRepository
from app.db.user_repository import UserRepository
from app.domain.job import JobRequirements
from app.main import app
from app.security.auth import get_current_user, hash_password
from app.workers.queue import AtlasTaskQueue

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


class FakeAPIClient:
    def extract_job(self, text: str) -> JobRequirements:
        return JobRequirements(title="Backend engineer")


@pytest.fixture
def repository() -> MongoResumeRepository:
    return MongoResumeRepository(mongomock.MongoClient()["api_test"])


@pytest.fixture
async def client(repository: MongoResumeRepository) -> AsyncIterator[httpx.AsyncClient]:
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_malware_scanner] = lambda: (lambda _: True)
    app.dependency_overrides[get_llm_client] = FakeAPIClient
    app.dependency_overrides[get_queue] = lambda: AtlasTaskQueue(repository.database)
    app.dependency_overrides[get_current_user] = lambda: "test-user"
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
    assert response.json()["files"][0]["status"] == "queued"


@pytest.mark.anyio
async def test_job_description_accepts_role_title_override(
    client: httpx.AsyncClient,
    repository: MongoResumeRepository,
) -> None:
    session_id = (await client.post("/v1/sessions", json={})).json()["session_id"]

    response = await client.post(
        f"/v1/sessions/{session_id}/job-description",
        json={"text": "Must know Python", "title": "Machine Learning & Python Developer"},
    )

    assert response.status_code == 202
    title = response.json()["normalized_requirements"]["title"]
    assert title == "Machine Learning & Python Developer"

    session = repository.get_session(session_id)
    assert session is not None
    assert (
        session["job_description"]["normalized_json"]["title"]
        == "Machine Learning & Python Developer"
    )


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
async def test_status_reports_parsed_skills_count(
    client: httpx.AsyncClient,
    repository: MongoResumeRepository,
) -> None:
    session_id = (await client.post("/v1/sessions", json={})).json()["session_id"]
    candidate = repository.add_resume(
        session_id,
        filename="resume.txt",
        content_type="text/plain",
        size_bytes=4,
        checksum="b" * 64,
        storage_uri="local://b",
    )
    repository.save_extraction(
        candidate["id"],
        text="Python",
        page_count=1,
        ocr_used=False,
        warnings=[],
        parsed={"schema_version": "1.0", "skills": ["Python", "REST"]},
        provenance={"provider": "test", "model": "test", "prompt_version": "v1"},
    )

    status = await client.get(f"/v1/sessions/{session_id}/status")

    assert status.status_code == 200
    assert status.json()["total"] == 1
    assert status.json()["files"][0]["status"] == "parsed"
    assert status.json()["files"][0]["skills_count"] == 2


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


@pytest.mark.anyio
async def test_unauthenticated_request_is_rejected(
    repository: MongoResumeRepository,
) -> None:
    user_repository = UserRepository(repository.database)
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_user_repository] = lambda: user_repository
    app.dependency_overrides[get_settings] = lambda: Settings(auth_secret_key="test-secret")
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as value:
        response = await value.post("/v1/sessions", json={})
    assert response.status_code == 401
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_login_returns_token_and_me_resolves_user(
    repository: MongoResumeRepository,
) -> None:
    user_repository = UserRepository(repository.database)
    user_repository.create_user("recruiter", "recruiter@example.com", hash_password("password123"))

    app.dependency_overrides[get_user_repository] = lambda: user_repository
    app.dependency_overrides[get_settings] = lambda: Settings(auth_secret_key="test-secret")
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as value:
        bad = await value.post(
            "/v1/auth/login",
            json={"email": "recruiter@example.com", "password": "wrong"},
        )
        assert bad.status_code == 401

        unknown = await value.post(
            "/v1/auth/login",
            json={"email": "nobody@example.com", "password": "password123"},
        )
        assert unknown.status_code == 401

        login = await value.post(
            "/v1/auth/login",
            json={"email": "recruiter@example.com", "password": "password123"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        assert token

        me = await value.get(
            "/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert me.status_code == 200
        assert me.json() == {"username": "recruiter"}
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_signup_creates_user_with_email_and_checks_uniqueness(
    repository: MongoResumeRepository,
) -> None:
    user_repository = UserRepository(repository.database)

    app.dependency_overrides[get_user_repository] = lambda: user_repository
    app.dependency_overrides[get_settings] = lambda: Settings(auth_secret_key="test-secret")
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as value:
        ok = await value.post(
            "/v1/auth/signup",
            json={
                "username": "newbie",
                "email": "newbie@example.com",
                "password": "password123",
            },
        )
        assert ok.status_code == 201
        assert ok.json()["username"] == "newbie"
        assert ok.json()["access_token"]

        # Duplicate username
        dup_username = await value.post(
            "/v1/auth/signup",
            json={
                "username": "newbie",
                "email": "other@example.com",
                "password": "password123",
            },
        )
        assert dup_username.status_code == 409

        # Duplicate email
        dup_email = await value.post(
            "/v1/auth/signup",
            json={
                "username": "someone",
                "email": "newbie@example.com",
                "password": "password123",
            },
        )
        assert dup_email.status_code == 409

        # Invalid email
        bad_email = await value.post(
            "/v1/auth/signup",
            json={
                "username": "another",
                "email": "not-an-email",
                "password": "password123",
            },
        )
        assert bad_email.status_code == 422
    app.dependency_overrides.clear()
