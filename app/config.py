from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str = "mongodb+srv://cluster.example"
    mongo_database: str = "resume_screener"
    object_storage_bucket: str = "resume-files"
    local_storage_root: str = ".data/resumes"
    llm_provider: str = "disabled"
    llm_model: str = ""
    llm_api_key: str | None = Field(default=None, repr=False)
    clamav_host: str = "127.0.0.1"
    clamav_port: int = Field(default=3310, ge=1, le=65535)
    clamav_socket: str | None = None
    max_file_bytes: int = Field(default=10 * 1024 * 1024, gt=0, le=10 * 1024 * 1024)
    retention_days: int = Field(default=30, ge=0, le=365)
    llm_timeout: float = Field(default=30.0, gt=0, le=120.0)
    auth_secret_key: str = Field(default="", repr=False)
    auth_token_expiry_minutes: int = Field(default=1440, ge=1, le=43200)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
