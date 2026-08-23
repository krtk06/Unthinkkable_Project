#!/usr/bin/env python3
"""Scheduled retention cleanup for expired resume files and sessions.

This script can be run periodically (e.g., via cron) to remove original
resume files that have passed their TTL and to log any dead-letter jobs.

Usage:
    python -m scripts.cleanup_retention
"""

import logging
import pathlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.config import get_settings
from app.db.client import create_mongo_client
from app.db.mongo_repository import MongoResumeRepository
from app.ingestion.storage import LocalFileStorage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan() -> AsyncIterator[tuple[MongoResumeRepository, LocalFileStorage]]:
    settings = get_settings()
    client = create_mongo_client(settings)
    db = client[settings.mongo_database]
    repo = MongoResumeRepository(db)
    storage = LocalFileStorage(pathlib.Path(settings.local_storage_root))
    try:
        yield repo, storage
    finally:
        client.close()


async def main() -> None:
    async with lifespan() as (repo, storage):
        # Clean up expired resume files (originals)
        deleted_files = repo.cleanup_expired_files(storage)
        logger.info("Retention cleanup: deleted %d expired resume files", deleted_files)

        # Report dead-letter jobs (failed with retries exhausted)
        from app.workers.queue import AtlasTaskQueue

        AtlasTaskQueue(repo.database)
        dead_jobs = list(repo.database.jobs.find({"status": "dead_letter"}))
        if dead_jobs:
            logger.warning("Dead-letter jobs found: %d", len(dead_jobs))
            for job in dead_jobs[:10]:
                logger.warning(
                    "  %%s: %%s (retries=%%d)",
                    job["_id"],
                    job.get("error_code"),
                    job.get("retry_count", 0),
                )
        else:
            logger.info("No dead-letter jobs found")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())