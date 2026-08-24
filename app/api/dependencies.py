from functools import lru_cache
from pathlib import Path

from app.config import Settings, get_settings
from app.db.client import create_mongo_client, get_database
from app.db.mongo_repository import MongoResumeRepository
from app.db.user_repository import UserRepository
from app.ingestion.storage import LocalFileStorage
from app.ingestion.text_extract import ExtractionResult, extract_text
from app.llm.client import OpenAITransport, StructuredLLMClient
from app.matching.embeddings import (
    EmbeddingClient,
    NullEmbeddingClient,
    OpenAIEmbeddingClient,
)
from app.security.clamav import ClamAVScanner
from app.workers.queue import AtlasTaskQueue
from app.workers.tasks import EmbeddingConfig, ModelConfig, ResumeWorker


@lru_cache(maxsize=1)
def get_repository() -> MongoResumeRepository:
    settings: Settings = get_settings()
    client = create_mongo_client(settings)
    return MongoResumeRepository(
        get_database(client, settings), retention_days=settings.retention_days
    )


@lru_cache(maxsize=1)
def get_user_repository() -> UserRepository:
    settings: Settings = get_settings()
    client = create_mongo_client(settings)
    return UserRepository(get_database(client, settings))


@lru_cache(maxsize=1)
def get_storage() -> LocalFileStorage:
    return LocalFileStorage(Path(get_settings().local_storage_root))


@lru_cache(maxsize=1)
def get_malware_scanner() -> ClamAVScanner:
    settings = get_settings()
    return ClamAVScanner(
        settings.clamav_host, settings.clamav_port, settings.clamav_socket
    )


@lru_cache(maxsize=1)
def get_llm_client() -> StructuredLLMClient:
    settings = get_settings()
    if not settings.llm_api_key or not settings.llm_model:
        raise RuntimeError("OPENAI_CONFIGURATION_REQUIRED")
    return StructuredLLMClient(
        OpenAITransport(settings.llm_api_key, settings.llm_model),
        prompt_version="v1",
    )


class DefaultExtractor:
    """Adapter for the shared extraction pipeline used by the worker."""

    def extract(self, file_bytes: bytes, content_type: str) -> ExtractionResult:
        if not file_bytes:
            raise ValueError("empty file bytes")
        try:
            return extract_text(file_bytes, content_type)
        except Exception as exc:
            raise ValueError(f"extraction failed for {content_type}: {exc}") from exc


@lru_cache(maxsize=1)
def get_embedding_client() -> EmbeddingClient:
    settings = get_settings()
    if settings.embedding_provider == "openai" and settings.embedding_model:
        api_key = settings.embedding_api_key or settings.llm_api_key
        if api_key:
            return OpenAIEmbeddingClient(api_key, settings.embedding_model)
    return NullEmbeddingClient()


@lru_cache(maxsize=1)
def get_worker() -> ResumeWorker:
    settings = get_settings()
    embedding_client = get_embedding_client()
    return ResumeWorker(
        get_repository(),
        get_storage(),
        DefaultExtractor(),
        get_llm_client(),
        model_config=ModelConfig(
            provider="openai",
            model=settings.llm_model,
            prompt_version="v1",
        ),
        embedding_config=EmbeddingConfig(
            client=embedding_client,
            model=settings.embedding_model,
            threshold=settings.shortlist_threshold,
        ),
    )


@lru_cache(maxsize=1)
def get_queue() -> AtlasTaskQueue:
    settings = get_settings()
    return AtlasTaskQueue(get_database(create_mongo_client(settings), settings))
