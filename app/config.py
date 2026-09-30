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

    # Trained models (ml/), published to Hugging Face. Off by default: pulling them in means a
    # multi-hundred-MB download + torch/transformers import on first use. When off, the app runs
    # exactly as before (regex extraction, rule-engine-only risk, template recommendation).
    ml_models_enabled: bool = False
    ml_extraction_model: str = "HarshilDaGoat/gem-certificate-extractor"
    ml_risk_model: str = "HarshilDaGoat/gem-bid-risk"
    ml_recommendation_model: str = "HarshilDaGoat/gem-recommendation-writer"
    ml_device: str | None = None  # None: cuda if available, else cpu

    # Comma-separated browser origins allowed to call this API (app/main.py's CORSMiddleware).
    # localhost:5173 (the Vite dev server) is always allowed in addition to whatever's listed
    # here, so this only needs the deployed frontend's origin, e.g. https://your-app.vercel.app
    cors_origins: str = ""

    # Serverless platforms (Cloud Run and similar) throttle CPU to near-zero between requests
    # unless you pay for "always allocated" CPU, which would starve a background Celery worker
    # idling on Redis. When true, /verify runs the pipeline inline within the request instead
    # of enqueueing it -- slower to respond, but correct on that kind of platform. Local dev
    # and docker-compose (a real always-on worker) should leave this off.
    sync_pipeline: bool = False

    # Connections kept open per API process (see app/db/session.py). 0 = no pooling, which the
    # Celery worker and Supabase's transaction pooler both need; the API-only deploy images set it.
    db_pool_size: int = 0


@lru_cache
def get_settings() -> Settings:
    return Settings()
