"""Celery task entry points. Every adapter/OCR/AI call happens inside these tasks, never
inline in a request handler (BUILD_SPEC.md section 1)."""
import asyncio
import logging

from celery import Task
from celery.result import AsyncResult

from app.celery_app import celery_app
from app.services.ocr import run_ocr_for_document
from app.services.orchestrator import run_pipeline_standalone

logger = logging.getLogger(__name__)


@celery_app.task(name="verify_bid")
def verify_bid_task(bid_id: str) -> dict:
    return asyncio.run(run_pipeline_standalone(bid_id))


@celery_app.task(name="ocr_document")
def ocr_document_task(doc_id: str) -> dict:
    return asyncio.run(run_ocr_for_document(doc_id))


def enqueue(task: Task, *, args: list, task_id: str) -> bool:
    """Publish a task, failing within seconds (not hanging) if the broker is unreachable.

    kombu's default producer connection retries forever even with retry=False, which left
    request handlers hanging whenever Redis was down; this bounds that to one retry.
    """
    try:
        with celery_app.connection_for_write() as conn:
            conn.ensure_connection(max_retries=1, interval_start=0, interval_step=0, timeout=3)
            # Task ids are reused (verify's is the bid_id), so drop the previous run's stored
            # result first: otherwise /status reports that stale SUCCESS until the worker picks
            # the new job up, and a poller takes the old result for the new one. Done before
            # publishing so it can never erase the new run's own result.
            AsyncResult(task_id, app=celery_app).forget()
            task.apply_async(args=args, task_id=task_id, connection=conn, retry=False)
        return True
    except Exception:
        logger.warning("Could not enqueue %s (%s): broker unreachable", task.name, task_id, exc_info=True)
        return False
