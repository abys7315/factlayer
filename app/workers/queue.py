"""Redis-backed job queue with concurrency control."""

from __future__ import annotations

import asyncio
import signal
import sys
import logging

from app.config import get_settings
from app.storage.redis_manager import RedisManager
from app.workers.pipeline import IngestionPipeline

logger = logging.getLogger(__name__)


class WorkerQueue:
    """
    Redis-backed worker queue for document processing.
    Supports priority queuing and concurrency limits.
    """

    QUEUE_NAME = "document_processing"
    POLL_INTERVAL = 2  # seconds

    def __init__(self):
        self.settings = get_settings()
        self.redis = RedisManager()
        self.pipeline = IngestionPipeline()
        self._running = True

    async def run(self):
        """Main worker loop — poll queue and process jobs."""
        logger.info(f"worker.started: concurrency={self.settings.WORKER_CONCURRENCY}")

        # Graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._shutdown)
            except NotImplementedError:
                pass

        semaphore = asyncio.Semaphore(self.settings.WORKER_CONCURRENCY)

        while self._running:
            try:
                job = await self.redis.dequeue_job(self.QUEUE_NAME)
                if job:
                    asyncio.create_task(
                        self._process_with_semaphore(semaphore, job)
                    )
                else:
                    await asyncio.sleep(self.POLL_INTERVAL)
            except Exception as e:
                logger.error(f"worker.poll_error: {e}")
                await asyncio.sleep(self.POLL_INTERVAL)

        logger.info("worker.stopped")

    async def _process_with_semaphore(self, semaphore: asyncio.Semaphore, job: dict):
        """Process a job within the concurrency semaphore."""
        async with semaphore:
            document_id = job.get("document_id", "")
            file_path = job.get("file_path", "")

            logger.info(f"worker.processing: document_id={document_id}")

            try:
                await self.redis.set_job_status(document_id, {"status": "RUNNING"})
                metrics = await self.pipeline.process_document(document_id, file_path)
                await self.redis.set_job_status(document_id, {"status": "COMPLETED", "metrics": metrics})
                logger.info(f"worker.completed: document_id={document_id} facts={metrics.get('facts_extracted', 0)}")
            except Exception as e:
                logger.error(f"worker.failed: document_id={document_id} error={e}")
                await self.redis.set_job_status(document_id, {"status": "FAILED", "error": str(e)[:500]})

    def _shutdown(self):
        logger.info("worker.shutting_down")
        self._running = False


async def main():
    worker = WorkerQueue()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
