"""Celery task entry points. Every adapter/OCR/AI call happens inside run_pipeline_standalone,
never inline in a request handler (BUILD_SPEC.md section 1)."""
import asyncio

from app.celery_app import celery_app
from app.services.orchestrator import run_pipeline_standalone


@celery_app.task(name="verify_bid")
def verify_bid_task(bid_id: str) -> dict:
    return asyncio.run(run_pipeline_standalone(bid_id))
