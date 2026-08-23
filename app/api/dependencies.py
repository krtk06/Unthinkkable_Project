from functools import lru_cache
from pathlib import Path

from app.config import Settings, get_settings
from app.db.client import create_mongo_client, get_database
from app.db.mongo_repository import MongoResumeRepository
from app.ingestion.storage import LocalFileStorage
from app.llm.client import OpenAITransport, StructuredLLMClient
from app.security.clamav import ClamAVScanner


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


@lru_cache(maxsize=1)
def get_malware_scanner() -> ClamAVScanner:
    settings = get_settings()
    return ClamAVScanner(settings.clamav_host, settings.clamav_port)


@lru_cache(maxsize=1)
def get_llm_client() -> StructuredLLMClient:
    settings = get_settings()
    if not settings.llm_api_key or not settings.llm_model:
        raise RuntimeError("OPENAI_CONFIGURATION_REQUIRED")
    return StructuredLLMClient(
        OpenAITransport(settings.llm_api_key, settings.llm_model),
        prompt_version="v1",
    )
