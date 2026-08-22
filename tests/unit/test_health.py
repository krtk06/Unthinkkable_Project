import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.main import app


@pytest.mark.anyio
async def test_health_endpoint_reports_service_status() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_resume_schema_endpoint_exposes_required_contract() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/schemas/extracted-resume")

    assert response.status_code == 200
    assert response.json()["required"] == [
        "schema_version",
        "candidate",
        "skills",
        "experience",
        "education",
        "certifications",
        "warnings",
    ]


def test_settings_reject_non_positive_file_limit() -> None:
    with pytest.raises(ValidationError):
        Settings(max_file_bytes=0)


def test_settings_default_to_local_mongodb() -> None:
    settings = Settings()

    assert settings.mongo_uri == "mongodb://localhost:27017"
    assert settings.mongo_database == "resume_screener"
