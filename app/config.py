from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://gem:gem@localhost:5432/gem_compliance"
    redis_url: str = "redis://localhost:6379/0"
    adapter_mode: str = "mock"
    seed_data_dir: Path = Path("WORKING DOCUMENTS")
    storage_dir: Path = Path("storage")
    # Unset means "tesseract" on PATH; on Windows the UB-Mannheim default path is also tried.
    tesseract_cmd: str | None = None
    max_upload_mb: int = 10
    ocr_max_pages: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
