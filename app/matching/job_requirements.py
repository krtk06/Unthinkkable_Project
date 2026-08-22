from app.domain.job import JobRequirements
from app.llm.client import LLMClient


def normalize_job_description(
    source: str | JobRequirements, client: LLMClient | None
) -> JobRequirements:
    if isinstance(source, JobRequirements):
        return source
    if not source.strip():
        raise ValueError("EMPTY_JOB_DESCRIPTION")
    if client is None:
        raise ValueError("LLM_CLIENT_REQUIRED")
    return client.extract_job(source)
