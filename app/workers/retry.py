"""Stage-level retry logic."""

from __future__ import annotations

import asyncio
import logging

from app.models.enums import PIPELINE_STAGES

logger = logging.getLogger(__name__)


class RetryManager:
    """
    Stage-level retry with exponential backoff.
    Failed stages can be retried independently.
    """

    def __init__(self, max_retries: int = 3, base_backoff: float = 2.0):
        self.max_retries = max_retries
        self.base_backoff = base_backoff

    async def with_retry(self, stage_name: str, func, *args, **kwargs):
        """Execute a function with retry logic."""
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt >= self.max_retries:
                    logger.error(f"retry.exhausted: stage={stage_name} attempt={attempt} error={e}")
                    raise
                wait = self.base_backoff ** attempt
                logger.warning(f"retry.attempt: stage={stage_name} attempt={attempt + 1} wait={wait} error={str(e)[:200]}")
                await asyncio.sleep(wait)

    def get_resume_stage(self, last_successful: str | None) -> int:
        """Get the stage index to resume from after failure."""
        if not last_successful:
            return 0
        try:
            idx = PIPELINE_STAGES.index(last_successful)
            return idx + 1
        except ValueError:
            return 0
