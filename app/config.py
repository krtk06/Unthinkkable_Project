from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://resume:resume@localhost:5432/resume_screener"
    object_storage_bucket: str = "resume-files"
    llm_provider: str = "disabled"
    llm_model: str = ""
    llm_api_key: str | None = Field(default=None, repr=False)
    max_file_bytes: int = 10 * 1024 * 1024
    retention_days: int = Field(default=30, ge=0, le=365)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
