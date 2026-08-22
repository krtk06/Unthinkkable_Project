from typing import Protocol

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
