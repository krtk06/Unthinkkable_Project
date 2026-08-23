import hashlib
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_malware_scanner, get_repository, get_storage
from app.config import get_settings
from app.db.mongo_repository import MongoResumeRepository
from app.ingestion.storage import LocalFileStorage
from app.ingestion.validation import UploadValidationError, validate_upload
from app.security.clamav import ClamAVScanner

router = APIRouter(prefix="/v1", tags=["screening"])


class CreateSessionRequest(BaseModel):
    job_description: str | None = None
    normalized_requirements: dict[str, Any] | None = None


class JobDescriptionRequest(BaseModel):
    text: str = Field(min_length=1)


def api_error(code: str, message: str, http_status: int) -> HTTPException:
    return HTTPException(
        http_status, {"error": {"code": code, "message": message, "details": {}}}
    )


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_session(
    request: CreateSessionRequest,
    repository: Annotated[MongoResumeRepository, Depends(get_repository)],
) -> dict[str, str]:
    session_id = repository.create_session()
    if request.job_description:
        repository.save_job_description(
            session_id, request.job_description, request.normalized_requirements or {}
        )
    return {"session_id": session_id}


@router.post("/sessions/{session_id}/job-description", status_code=status.HTTP_202_ACCEPTED)
def save_job_description(
    session_id: str,
    request: JobDescriptionRequest,
    repository: Annotated[MongoResumeRepository, Depends(get_repository)],
) -> dict[str, str]:
    try:
        repository.save_job_description(session_id, request.text, {})
    except ValueError as error:
        if str(error) == "SESSION_NOT_FOUND":
            raise api_error("SESSION_NOT_FOUND", "Screening session was not found", 404) from error
        raise
    return {"session_id": session_id, "status": "accepted"}


@router.post("/sessions/{session_id}/resumes", status_code=status.HTTP_202_ACCEPTED)
async def upload_resumes(
    session_id: str,
    files: Annotated[list[UploadFile], File(...)],
    repository: Annotated[MongoResumeRepository, Depends(get_repository)],
    storage: Annotated[LocalFileStorage, Depends(get_storage)],
    scanner: Annotated[ClamAVScanner, Depends(get_malware_scanner)],
) -> dict[str, Any]:
    if repository.get_session(session_id) is None:
        raise api_error("SESSION_NOT_FOUND", "Screening session was not found", 404)
    if len(files) > 100:
        raise api_error("BATCH_TOO_LARGE", "A batch may contain at most 100 files", 400)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
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
        accepted.append({"candidate_id": candidate["id"], "status": "uploaded"})
    return {
        "session_id": session_id,
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
) -> dict[str, Any]:
    try:
        candidates = repository.list_candidates(session_id)
    except ValueError as error:
        if str(error) == "SESSION_NOT_FOUND":
            raise api_error("SESSION_NOT_FOUND", "Screening session was not found", 404) from error
        raise
    matches = [candidate["match"] for candidate in candidates if candidate.get("match")]
    if threshold is not None:
        matches = [match for match in matches if match.get("score", 0) >= threshold]
    if min_score is not None:
        matches = [match for match in matches if match.get("score", 0) >= min_score]
    if max_score is not None:
        matches = [match for match in matches if match.get("score", 0) <= max_score]
    matches.sort(key=lambda match: (-match.get("score", 0), match["candidate_id"]))
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
