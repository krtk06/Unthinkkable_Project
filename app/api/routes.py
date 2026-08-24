import hashlib
from typing import Annotated, Any, cast
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field

from app.api.dependencies import (
    get_llm_client,
    get_malware_scanner,
    get_queue,
    get_repository,
    get_storage,
    get_worker,
)
from app.config import get_settings
from app.db.mongo_repository import MongoResumeRepository
from app.domain.job import JobRequirements
from app.ingestion.storage import LocalFileStorage
from app.ingestion.text_extract import extract_text
from app.ingestion.validation import UploadValidationError, validate_upload
from app.llm.client import LLMClient
from app.matching.scoring import ScoringClient
from app.security.auth import get_current_user
from app.security.clamav import ClamAVScanner
from app.workers.queue import AtlasTaskQueue
from app.workers.tasks import ResumeWorker

router = APIRouter(
    prefix="/v1",
    tags=["screening"],
    dependencies=[Depends(get_current_user)],
)


class CreateSessionRequest(BaseModel):
    job_description: str | None = None
    normalized_requirements: dict[str, Any] | None = None


class JobDescriptionRequest(BaseModel):
    text: str = Field(min_length=1)


def api_error(code: str, message: str, http_status: int) -> HTTPException:
    return HTTPException(
        http_status, {"error": {"code": code, "message": message, "details": {}}}
    )


def rescore_session(
    repository: MongoResumeRepository,
    queue: AtlasTaskQueue,
    session_id: str,
) -> None:
    repository.reset_scoring_for_session(session_id)
    for candidate in repository.list_candidates(session_id):
        if candidate.get("resume", {}).get("status") == "parsed":
            queue.enqueue(
                "process_candidate",
                {"candidate_id": candidate["id"]},
                session_id,
            )


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_session(
    request: CreateSessionRequest,
    repository: Annotated[MongoResumeRepository, Depends(get_repository)],
    llm_client: Annotated[LLMClient, Depends(get_llm_client)],
) -> dict[str, Any]:
    session_id = repository.create_session()
    if request.job_description:
        normalized = request.normalized_requirements
        if normalized is None:
            normalized = llm_client.extract_job(request.job_description).model_dump(mode="json")
        repository.save_job_description(
            session_id, request.job_description, normalized
        )
    return {"session_id": session_id}


@router.post("/sessions/{session_id}/job-description", status_code=status.HTTP_202_ACCEPTED)
def save_job_description(
    session_id: str,
    request: JobDescriptionRequest,
    repository: Annotated[MongoResumeRepository, Depends(get_repository)],
    llm_client: Annotated[LLMClient, Depends(get_llm_client)],
    queue: Annotated[AtlasTaskQueue, Depends(get_queue)],
) -> dict[str, Any]:
    try:
        normalized = llm_client.extract_job(request.text)
        repository.save_job_description(
            session_id, request.text, normalized.model_dump(mode="json")
        )
        rescore_session(repository, queue, session_id)
    except ValueError as error:
        if str(error) == "SESSION_NOT_FOUND":
            raise api_error("SESSION_NOT_FOUND", "Screening session was not found", 404) from error
        raise
    return {
        "session_id": session_id,
        "status": "accepted",
        "normalized_requirements": normalized.model_dump(mode="json"),
    }


@router.post("/sessions/{session_id}/job-description/file", status_code=status.HTTP_202_ACCEPTED)
async def upload_job_description_file(
    session_id: str,
    file: UploadFile,
    repository: Annotated[MongoResumeRepository, Depends(get_repository)],
    llm_client: Annotated[LLMClient, Depends(get_llm_client)],
    queue: Annotated[AtlasTaskQueue, Depends(get_queue)],
) -> dict[str, Any]:
    if repository.get_session(session_id) is None:
        raise api_error("SESSION_NOT_FOUND", "Screening session was not found", 404)
    content_type = file.content_type or "application/octet-stream"
    allowed_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    }
    if content_type not in allowed_types:
        raise api_error(
            "UNSUPPORTED_FILE_TYPE",
            "Only PDF, DOCX, and plain text files are accepted for job descriptions",
            400,
        )
    contents = await file.read()
    if len(contents) == 0:
        raise api_error("EMPTY_FILE", "The uploaded file is empty", 400)
    if len(contents) > get_settings().max_file_bytes:
        raise api_error("FILE_TOO_LARGE", "File exceeds the size limit", 400)
    try:
        extraction = extract_text(contents, content_type)
    except ValueError as error:
        raise api_error("EXTRACTION_FAILED", str(error), 400) from error
    if not extraction.text.strip():
        raise api_error("NO_EXTRACTABLE_TEXT", "No text could be extracted from the file", 400)
    try:
        normalized = llm_client.extract_job(extraction.text)
        repository.save_job_description(
            session_id, extraction.text, normalized.model_dump(mode="json")
        )
        rescore_session(repository, queue, session_id)
    except ValueError as error:
        if str(error) == "SESSION_NOT_FOUND":
            raise api_error("SESSION_NOT_FOUND", "Screening session was not found", 404) from error
        raise
    return {
        "session_id": session_id,
        "status": "accepted",
        "normalized_requirements": normalized.model_dump(mode="json"),
    }


@router.post("/sessions/{session_id}/resumes", status_code=status.HTTP_202_ACCEPTED)
async def upload_resumes(
    session_id: str,
    files: Annotated[list[UploadFile], File(...)],
    repository: Annotated[MongoResumeRepository, Depends(get_repository)],
    storage: Annotated[LocalFileStorage, Depends(get_storage)],
    scanner: Annotated[ClamAVScanner, Depends(get_malware_scanner)],
    queue: Annotated[AtlasTaskQueue, Depends(get_queue)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict[str, Any]:
    if repository.get_session(session_id) is None:
        raise api_error("SESSION_NOT_FOUND", "Screening session was not found", 404)
    if len(files) > 100:
        raise api_error("BATCH_TOO_LARGE", "A batch may contain at most 100 files", 400)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    batch_id = uuid4().hex
    for file in files:
        contents = await file.read()
        content_type = file.content_type or "application/octet-stream"
        try:
            validate_upload(
                file.filename or "",
                content_type,
                len(contents),
                max_file_bytes=get_settings().max_file_bytes,
                file_bytes=contents,
                malware_scanner=scanner,
            )
            checksum = hashlib.sha256(contents).hexdigest()
            uri = storage.put_original(contents, checksum, content_type)
            candidate = repository.add_resume(
                session_id,
                filename=file.filename or "",
                content_type=content_type,
                size_bytes=len(contents),
                checksum=checksum,
                storage_uri=uri,
                idempotency_key=idempotency_key,
            )
        except UploadValidationError as error:
            rejected.append(
                {
                    "filename": file.filename or "",
                    "status": "failed",
                    "error": {"code": error.code, "message": str(error), "details": {}},
                }
            )
            continue
        except ValueError as error:
            if str(error) == "DUPLICATE_RESUME":
                rejected.append(
                    {
                        "filename": file.filename or "",
                        "status": "failed",
                        "error": {
                            "code": "DUPLICATE_RESUME",
                            "message": "Resume already exists in this session",
                            "details": {},
                        },
                    }
                )
                continue
            raise
        accepted.append(
            {
                "candidate_id": candidate["id"],
                "job_id": candidate["job_id"],
                "status": candidate["resume"]["status"],
            }
        )
        job_id = queue.enqueue(
            "process_candidate",
            {"candidate_id": candidate["id"], "idempotency_key": idempotency_key},
            batch_id,
        )
        accepted[-1]["job_id"] = job_id
    return {
        "session_id": session_id,
        "batch_id": batch_id,
        "accepted": len(accepted),
        "rejected": len(rejected),
        "files": [*accepted, *rejected],
    }


@router.get("/sessions/{session_id}/status")
def session_status(
    session_id: str,
    repository: Annotated[MongoResumeRepository, Depends(get_repository)],
) -> dict[str, Any]:
    try:
        candidates = repository.list_candidates(session_id)
    except ValueError as error:
        if str(error) == "SESSION_NOT_FOUND":
            raise api_error("SESSION_NOT_FOUND", "Screening session was not found", 404) from error
        raise
    counts: dict[str, int] = {}
    for candidate in candidates:
        current = str(candidate["resume"]["status"])
        counts[current] = counts.get(current, 0) + 1
    return {
        "session_id": session_id,
        "total": len(candidates),
        "counts": counts,
        "files": [
            {
                "candidate_id": candidate["id"],
                "filename": candidate["resume"].get("filename"),
                "status": candidate["resume"].get("status"),
                "error_code": candidate["resume"].get("error_code"),
            }
            for candidate in candidates
        ],
    }


@router.get("/sessions/{session_id}/matches")
def session_matches(
    session_id: str,
    repository: Annotated[MongoResumeRepository, Depends(get_repository)],
    threshold: int | None = None,
    top_n: int | None = None,
    min_score: int | None = None,
    max_score: int | None = None,
    cursor: str | None = None,
    limit: int = 50,
    min_required_coverage: float | None = None,
    min_preferred_coverage: float | None = None,
    status: str | None = None,
    location: str | None = None,
    work_mode: str | None = None,
    required_skills_complete: bool | None = None,
    min_experience_months: int | None = None,
) -> dict[str, Any]:
    try:
        candidates = repository.list_candidates(session_id)
    except ValueError as error:
        if str(error) == "SESSION_NOT_FOUND":
            raise api_error("SESSION_NOT_FOUND", "Screening session was not found", 404) from error
        raise
    matches = [
        {
            **candidate["match"],
            "_metadata": {
                "status": candidate["resume"].get("status"),
                "location": (
                    candidate.get("resume", {})
                    .get("parsed_json", {})
                    .get("candidate", {})
                    .get("location")
                ),
                "work_mode": candidate.get("resume", {}).get("parsed_json", {}).get("work_mode"),
                "required_skills_complete": candidate.get("resume", {})
                .get("parsed_json", {})
                .get("required_skills_complete"),
                "experience_months": candidate.get("resume", {})
                .get("parsed_json", {})
                .get("experience_months", 0),
            },
        }
        for candidate in candidates
        if candidate.get("match")
    ]
    if threshold is not None:
        matches = [match for match in matches if match.get("score", 0) >= threshold]
    if min_score is not None:
        matches = [match for match in matches if match.get("score", 0) >= min_score]
    if max_score is not None:
        matches = [match for match in matches if match.get("score", 0) <= max_score]
    matches = [
        match
        for match in matches
        if min_required_coverage is None
        or match.get("required_coverage", 0) >= min_required_coverage
    ]
    if required_skills_complete is not None:
        matches = [
            match
            for match in matches
            if match["_metadata"].get("required_skills_complete") == required_skills_complete
        ]
    if min_experience_months is not None:
        matches = [
            match
            for match in matches
            if match["_metadata"].get("experience_months", 0) >= min_experience_months
        ]
    matches = [
        match
        for match in matches
        if min_preferred_coverage is None
        or match.get("preferred_coverage", 0) >= min_preferred_coverage
    ]
    matches = [
        match
        for match in matches
        if status is None or match["_metadata"].get("status") == status
    ]
    matches = [
        match
        for match in matches
        if location is None or match["_metadata"].get("location") == location
    ]
    matches = [
        match
        for match in matches
        if work_mode is None or match["_metadata"].get("work_mode") == work_mode
    ]
    matches.sort(
        key=lambda match: (
            -match.get("score", 0),
            -match.get("required_coverage", 0),
            match["candidate_id"],
        )
    )
    if threshold is not None and top_n is not None:
        raise api_error("THRESHOLD_TOP_N_CONFLICT", "Choose threshold or top_n", 400)
    if top_n is not None:
        matches = matches[:top_n]
    if limit < 1 or limit > 100:
        raise api_error("INVALID_LIMIT", "limit must be between 1 and 100", 400)
    if cursor is not None:
        try:
            cursor_score, cursor_coverage, cursor_id = cursor.split(":", 2)
            cursor_key = (-int(cursor_score), -float(cursor_coverage), cursor_id)
        except ValueError as error:
            raise api_error("INVALID_CURSOR", "Cursor is malformed", 400) from error
        matches = [
            match
            for match in matches
            if (-match.get("score", 0), -match.get("required_coverage", 0), match["candidate_id"])
            > cursor_key
        ]
    page = matches[:limit]
    next_cursor = None
    if len(matches) > limit:
        last = page[-1]
        next_cursor = f"{last['score']}:{last.get('required_coverage', 0)}:{last['candidate_id']}"
    for match in page:
        match.pop("_metadata", None)
    return {"session_id": session_id, "matches": page, "next_cursor": next_cursor}


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
    
    normalized = ((session or {}).get("job_description") or {}).get("normalized_json")
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
        "required_coverage": result.required_coverage,
        "preferred_coverage": result.preferred_coverage,
        "strengths": result.strengths,
        "gaps": result.gaps,
    }


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
