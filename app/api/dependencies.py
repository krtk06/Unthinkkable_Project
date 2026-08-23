from functools import lru_cache
from pathlib import Path

from app.config import Settings, get_settings
from app.db.client import create_mongo_client, get_database
from app.db.mongo_repository import MongoResumeRepository
from app.ingestion.storage import LocalFileStorage


@lru_cache(maxsize=1)
def get_repository() -> MongoResumeRepository:
    settings: Settings = get_settings()
    client = create_mongo_client(settings)
    return MongoResumeRepository(
        get_database(client, settings), retention_days=settings.retention_days
    )


@lru_cache(maxsize=1)
def get_storage() -> LocalFileStorage:
    return LocalFileStorage(Path(get_settings().local_storage_root))
