from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_repository, get_storage, get_worker
from app.api.routes import api_error
from app.db.mongo_repository import MongoResumeRepository
from app.domain.job import JobRequirements
from app.ingestion.storage import LocalFileStorage
from app.matching.scoring import ScoringClient
from app.workers.tasks import ResumeWorker

router = APIRouter(
    prefix="/v1",
    tags=["screening"],
    dependencies=[],
)


def _get_nested(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = data
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key, default)
        if cur is default:
            return default
    return cur


@router.get("/candidates/{candidate_id}")
def candidate_detail(
    candidate_id: str,
    repository: Annotated[MongoResumeRepository, Depends(get_repository)],
) -> dict[str, Any]:
    candidate = repository.get_candidate(candidate_id)
    if candidate is None:
        raise api_error("CANDIDATE_NOT_FOUND", "Candidate was not found", 404)
    return {"candidate_id": candidate_id, **candidate}


@router.post("/candidates/{candidate_id}/score", status_code=status.HTTP_202_ACCEPTED)
def score_single_candidate(
    candidate_id: str,
    repository: Annotated[MongoResumeRepository, Depends(get_repository)],
    worker: Annotated[ResumeWorker, Depends(get_worker)],
) -> dict[str, Any]:
    candidate = repository.get_candidate(candidate_id)
    if candidate is None:
        raise api_error("CANDIDATE_NOT_FOUND", "Candidate was not found", 404)

    session = repository.get_session(candidate["session_id"])
    if session is None:
        raise api_error("SESSION_NOT_FOUND", "Screening session was not found", 404)

    normalized = _get_nested(session, "job_description", "normalized_json")
    if not normalized:
        raise api_error("NO_JOB_DESCRIPTION", "No job description available for scoring", 400)

    requirements = JobRequirements.model_validate(normalized)

    result = worker.score_candidate(
        candidate_id=candidate_id,
        requirements=requirements,
        client=cast(ScoringClient, worker.parser),
    )

    return {
        "candidate_id": candidate_id,
        "score": result.score,
        "skills_score": result.skills_score,
        "experience_score": result.experience_score,
        "education_score": result.education_score,
        "matching_skills": result.matching_skills,
        "missing_skills": result.missing_skills,
        "semantic_similarity": result.semantic_similarity,
        "analysis": result.analysis,
        "shortlisted": result.shortlisted,
    }


@router.delete("/candidates/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate(
    candidate_id: str,
    repository: Annotated[MongoResumeRepository, Depends(get_repository)],
    storage: Annotated[LocalFileStorage, Depends(get_storage)],
) -> None:
    candidate = repository.get_candidate(candidate_id)
    if candidate is None:
        raise api_error("CANDIDATE_NOT_FOUND", "Candidate was not found", 404)
    storage_uri = _get_nested(candidate, "resume", "storage_uri")
    if storage_uri:
        storage.delete_original(storage_uri)
    repository.remove_candidate(candidate_id)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: str,
    repository: Annotated[MongoResumeRepository, Depends(get_repository)],
    storage: Annotated[LocalFileStorage, Depends(get_storage)],
) -> None:
    session = repository.get_session(session_id)
    if session is None:
        raise api_error("SESSION_NOT_FOUND", "Screening session was not found", 404)
    for candidate in session.get("candidates", []):
        storage.delete_original(candidate["resume"]["storage_uri"])
    repository.delete_session(session_id)
