from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from pymongo import ASCENDING, ReturnDocument
from pymongo.database import Database


class AtlasTaskQueue:
    def __init__(
        self,
        database: Database[Any],
        *,
        lease_seconds: int = 300,
        max_attempts: int = 3,
    ) -> None:
        self.database = database
        self.jobs = database["jobs"]
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts
        self.jobs.create_index([("status", ASCENDING), ("created_at", ASCENDING)])
        self.jobs.create_index("batch_id")

    def enqueue(self, task: str, payload: dict[str, Any], batch_id: str | None = None) -> str:
        job_id = uuid4().hex
        now = datetime.now(UTC)
        self.jobs.insert_one(
            {
                "_id": job_id,
                "task": task,
                "payload": payload,
                "batch_id": batch_id,
                "status": "queued",
                "attempts": 0,
                "created_at": now,
                "updated_at": now,
            }
        )
        return job_id

    def claim(self, worker_id: str) -> dict[str, Any] | None:
        now = datetime.now(UTC)
        job = self.jobs.find_one_and_update(
            {
                "$or": [
                    {"status": "queued"},
                    {"status": "processing", "lease_until": {"$lt": now}},
                ]
            },
            {
                "$set": {
                    "status": "processing",
                    "worker_id": worker_id,
                    "lease_until": now + timedelta(seconds=self.lease_seconds),
                    "updated_at": now,
                },
                "$inc": {"attempts": 1},
            },
            sort=[("created_at", ASCENDING)],
            return_document=ReturnDocument.AFTER,
        )
        return cast(dict[str, Any] | None, job)

    def complete(self, job_id: str) -> None:
        self.jobs.update_one(
            {"_id": job_id, "status": "processing"},
            {
                "$set": {"status": "completed", "updated_at": datetime.now(UTC)},
                "$unset": {"lease_until": ""},
            },
        )

    def fail(self, job_id: str, error: str) -> None:
        job = self.jobs.find_one({"_id": job_id})
        if job is None:
            raise ValueError("JOB_NOT_FOUND")
        terminal = job.get("attempts", 0) >= self.max_attempts
        self.jobs.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": "dead_letter" if terminal else "queued",
                    "error": error,
                    "updated_at": datetime.now(UTC),
                },
                "$unset": {"lease_until": ""},
            },
        )

    def pending_count(self) -> int:
        return self.jobs.count_documents({"status": "queued"})
