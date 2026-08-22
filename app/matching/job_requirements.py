from typing import Protocol

from sqlalchemy.orm import Session

from app.db.repository import ResumeRepository
from app.domain.job import JobRequirements

class JobRequirementsClient(Protocol):
    def extract_job(self, text: str) -> JobRequirements: ...


def normalize_job_description(
    source: str | JobRequirements, client: JobRequirementsClient | None
) -> JobRequirements:
    if isinstance(source, JobRequirements):
        return source
    if not source.strip():
        raise ValueError("EMPTY_JOB_DESCRIPTION")
    if client is None:
        raise ValueError("LLM_CLIENT_REQUIRED")
    return client.extract_job(source)


def normalized_job_payload(requirements: JobRequirements) -> dict[str, object]:
    return requirements.model_dump(mode="json")


def normalize_and_persist_job_description(
    db: Session,
    repository: ResumeRepository,
    session_id: str,
    source: str | JobRequirements,
    client: JobRequirementsClient | None,
) -> JobRequirements:
    requirements = normalize_job_description(source, client)
    raw_text = source if isinstance(source, str) else requirements.model_dump_json()
    repository.save_job_description(
        db, session_id, raw_text, normalized_job_payload(requirements)
    )
    return requirements
