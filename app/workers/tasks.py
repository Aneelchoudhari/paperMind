"""Celery tasks — async ingestion worker."""
import asyncio

from app.workers.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_paper(self, paper_id: str) -> dict:
    """Background task: run the full ingestion pipeline for a paper."""
    logger.info("Celery task process_paper(%s) started", paper_id)
    try:
        # Celery workers are synchronous; we run async code in an event loop
        asyncio.run(_run_async(paper_id))
        logger.info("Celery task process_paper(%s) finished", paper_id)
        return {"paper_id": paper_id, "status": "done"}
    except Exception as exc:
        logger.exception("Task failed for paper %s: %s", paper_id, exc)
        raise self.retry(exc=exc)


async def _run_async(paper_id: str) -> None:
    """Create a DB session and run the ingestion service."""
    from app.db.session import AsyncSessionLocal
    from app.services.ingestion_service import run_ingestion

    async with AsyncSessionLocal() as db:
        await run_ingestion(paper_id, db)
