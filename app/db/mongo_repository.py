from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from pymongo import ASCENDING, ReturnDocument
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
        self.sessions.create_index([("candidates.resume.checksum", ASCENDING)])
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
            "resume": {**resume, "status": "uploaded", "attempts": [], "attempt_counters": {}},
        }
        result = self.sessions.update_one(
            {"_id": session_id, "candidates.resume.checksum": {"$ne": resume["checksum"]}},
            {"$push": {"candidates": candidate}, "$set": {"updated_at": datetime.now(UTC)}},
        )
        if result.matched_count == 0 and self.get_session(session_id) is None:
            raise ValueError("SESSION_NOT_FOUND")
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

    def claim_stage(self, candidate_id: str, expected: list[str], claimed: str) -> bool:
        result = self.sessions.update_one(
            {"candidates.id": candidate_id, "candidates.resume.status": {"$in": expected}},
            {"$set": {"candidates.$.resume.status": claimed}},
        )
        return result.modified_count == 1

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
        counter = self.sessions.find_one_and_update(
            {"candidates.id": candidate_id},
            {"$inc": {"candidates.$.resume.attempt_counters." + stage: 1}},
            projection={"candidates": {"$elemMatch": {"id": candidate_id}}},
            return_document=ReturnDocument.AFTER,
        )
        if counter is None:
            raise ValueError("CANDIDATE_NOT_FOUND")
        current = cast(dict[str, Any], counter["candidates"][0])
        attempt_number = current["resume"]["attempt_counters"][stage]
        self._update_candidate(
            candidate_id,
            {
                "resume.attempts": [
                    *current["resume"].get("attempts", []),
                    {
                        "stage": stage,
                        "status": status,
                        "attempt_number": attempt_number,
                        "error_code": error_code,
                        "created_at": datetime.now(UTC),
                    },
                ]
            },
        )

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

    def save_match(self, candidate_id: str, match: dict[str, Any]) -> bool:
        updated = self.sessions.update_one(
            {"candidates.id": candidate_id, "candidates.match": {"$exists": True}},
            {"$set": {"candidates.$.match": match, "candidates.$.resume.status": "scored"}},
        )
        if updated.modified_count == 1:
            return True
        result = self.sessions.update_one(
            {"candidates.id": candidate_id, "candidates.match": {"$exists": False}},
            {"$set": {"candidates.$.match": match, "candidates.$.resume.status": "scored"}},
        )
        return result.modified_count == 1

    def get_match(self, candidate_id: str) -> dict[str, Any] | None:
        candidate = self.get_candidate(candidate_id)
        if candidate is None:
            return None
        return candidate.get("match")

    def delete_session(self, session_id: str) -> None:
        self.sessions.delete_one({"_id": session_id})
