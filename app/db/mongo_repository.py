from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from pymongo import ASCENDING
from pymongo.database import Database


def _id() -> str:
    return uuid4().hex


class MongoResumeRepository:
    def __init__(
        self,
        database: Database[Any],
        *,
        retention_days: int = 30,
    ) -> None:
        self.database = database
        self.sessions = database["sessions"]
        self.retention_days = retention_days
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.sessions.create_index("expires_at", expireAfterSeconds=0)
        self.sessions.create_index([("candidates.checksum", ASCENDING)])
        self.sessions.create_index([("candidates.id", ASCENDING)])

    def create_session(self) -> str:
        session_id = _id()
        now = datetime.now(UTC)
        self.sessions.insert_one(
            {
                "_id": session_id,
                "status": "created",
                "created_at": now,
                "updated_at": now,
                "expires_at": now + timedelta(days=self.retention_days),
                "job_description": None,
                "candidates": [],
            }
        )
        return session_id

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        return cast(dict[str, Any] | None, self.sessions.find_one({"_id": session_id}))

    def add_resume(self, session_id: str, **resume: Any) -> dict[str, Any]:
        candidate = {
            "id": _id(),
            "session_id": session_id,
            "resume": {**resume, "status": "uploaded"},
        }
        result = self.sessions.update_one(
            {"_id": session_id, "candidates.checksum": {"$ne": resume["checksum"]}},
            {"$push": {"candidates": candidate}, "$set": {"updated_at": datetime.now(UTC)}},
        )
        if result.modified_count != 1:
            raise ValueError("DUPLICATE_RESUME")
        return candidate

    def get_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        record = self.sessions.find_one(
            {"candidates.id": candidate_id}, {"candidates": {"$elemMatch": {"id": candidate_id}}}
        )
        if record is None or not record.get("candidates"):
            return None
        return cast(dict[str, Any], record["candidates"][0])

    def get_resume(self, resume_id: str) -> dict[str, Any] | None:
        return self.get_candidate(resume_id)

    def _update_candidate(self, candidate_id: str, update: dict[str, Any]) -> None:
        result = self.sessions.update_one(
            {"candidates.id": candidate_id},
            {"$set": {f"candidates.$.{key}": value for key, value in update.items()}},
        )
        if result.matched_count != 1:
            raise ValueError("CANDIDATE_NOT_FOUND")

    def update_stage(self, candidate_id: str, status: str, error_code: str | None = None) -> None:
        self._update_candidate(
            candidate_id, {"resume.status": status, "resume.error_code": error_code}
        )

    def record_attempt(
        self,
        candidate_id: str,
        stage: str,
        status: str,
        *,
        error_code: str | None = None,
    ) -> None:
        candidate = self.get_candidate(candidate_id)
        if candidate is None:
            raise ValueError("CANDIDATE_NOT_FOUND")
        attempts = candidate.get("resume", {}).get("attempts", [])
        attempt_number = 1 + max(
            (item["attempt_number"] for item in attempts if item["stage"] == stage),
            default=0,
        )
        attempts.append(
            {
                "stage": stage,
                "status": status,
                "attempt_number": attempt_number,
                "error_code": error_code,
                "created_at": datetime.now(UTC),
            }
        )
        self._update_candidate(candidate_id, {"resume.attempts": attempts})

    def save_extraction(
        self,
        candidate_id: str,
        *,
        text: str,
        page_count: int,
        ocr_used: bool,
        warnings: list[str],
        parsed: dict[str, Any],
        provenance: dict[str, str],
    ) -> None:
        self._update_candidate(
            candidate_id,
            {
                "resume.extracted_text": text,
                "resume.page_count": page_count,
                "resume.ocr_used": ocr_used,
                "resume.extraction_warnings": warnings,
                "resume.parsed_json": parsed,
                "resume.extraction": provenance,
                "resume.status": "parsed",
            },
        )

    def save_embedding(self, candidate_id: str, vector: list[float], model: str) -> None:
        self._update_candidate(
            candidate_id, {"resume.embedding": vector, "resume.embedding_model": model}
        )

    def save_job_description(
        self, session_id: str, raw_text: str, normalized: dict[str, Any]
    ) -> None:
        result = self.sessions.update_one(
            {"_id": session_id},
            {
                "$set": {
                    "job_description": {"raw_text": raw_text, "normalized_json": normalized},
                    "updated_at": datetime.now(UTC),
                }
            },
        )
        if result.matched_count != 1:
            raise ValueError("SESSION_NOT_FOUND")

    def save_match(self, candidate_id: str, match: dict[str, Any]) -> None:
        self._update_candidate(candidate_id, {"match": match, "resume.status": "scored"})

    def get_match(self, candidate_id: str) -> dict[str, Any] | None:
        candidate = self.get_candidate(candidate_id)
        if candidate is None:
            return None
        return candidate.get("match")

    def delete_session(self, session_id: str) -> None:
        self.sessions.delete_one({"_id": session_id})
