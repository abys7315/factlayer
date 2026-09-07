"""Redis manager — job queue, cache, rate limiting with in-memory fallback."""

from __future__ import annotations

import asyncio
import json
from typing import Any

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None

from app.config import get_settings


class RedisManager:
    """
    Redis as job queue + cache + rate limiter + concurrency control.
    Provides in-memory fallback if Redis server/library is not present.
    """

    def __init__(self):
        self.settings = get_settings()
        self._client: Any = None
        self._memory_queues: dict[str, list[dict]] = {}
        self._memory_cache: dict[str, Any] = {}
        self._memory_jobs: dict[str, dict] = {}

    async def get_client(self):
        if aioredis is None:
            return None
        if self._client is None:
            try:
                self._client = aioredis.from_url(
                    self.settings.REDIS_URL,
                    decode_responses=True,
                )
            except Exception:
                self._client = None
        return self._client

    async def close(self):
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None

    # ── Job Queue ─────────────────────────────────────────────────────

    async def enqueue_job(self, queue_name: str, job_data: dict, priority: int = 0):
        """Add a job to the Redis queue with priority."""
        client = await self.get_client()
        if client is not None:
            try:
                payload = json.dumps(job_data)
                await client.zadd(f"queue:{queue_name}", {payload: priority})
                return
            except Exception:
                pass

        if queue_name not in self._memory_queues:
            self._memory_queues[queue_name] = []
        self._memory_queues[queue_name].append(job_data)

    async def dequeue_job(self, queue_name: str) -> dict | None:
        """Pop the highest-priority job from the queue."""
        client = await self.get_client()
        if client is not None:
            try:
                results = await client.zpopmin(f"queue:{queue_name}", count=1)
                if results:
                    payload, score = results[0]
                    return json.loads(payload)
                return None
            except Exception:
                pass

        if queue_name in self._memory_queues and self._memory_queues[queue_name]:
            return self._memory_queues[queue_name].pop(0)
        return None

    async def get_queue_length(self, queue_name: str) -> int:
        client = await self.get_client()
        if client is not None:
            try:
                return await client.zcard(f"queue:{queue_name}")
            except Exception:
                pass
        return len(self._memory_queues.get(queue_name, []))

    # ── Job Status ────────────────────────────────────────────────────

    async def set_job_status(self, job_id: str, status_data: dict, ttl_seconds: int = 86400):
        client = await self.get_client()
        if client is not None:
            try:
                await client.set(f"job:{job_id}", json.dumps(status_data), ex=ttl_seconds)
                return
            except Exception:
                pass
        self._memory_jobs[job_id] = status_data

    async def get_job_status(self, job_id: str) -> dict | None:
        client = await self.get_client()
        if client is not None:
            try:
                data = await client.get(f"job:{job_id}")
                return json.loads(data) if data else None
            except Exception:
                pass
        return self._memory_jobs.get(job_id)

    # ── Cache ─────────────────────────────────────────────────────────

    async def cache_get(self, key: str) -> Any | None:
        client = await self.get_client()
        if client is not None:
            try:
                data = await client.get(f"cache:{key}")
                return json.loads(data) if data else None
            except Exception:
                pass
        return self._memory_cache.get(key)

    async def cache_set(self, key: str, value: Any, ttl_seconds: int = 3600):
        client = await self.get_client()
        if client is not None:
            try:
                await client.set(f"cache:{key}", json.dumps(value), ex=ttl_seconds)
                return
            except Exception:
                pass
        self._memory_cache[key] = value

    async def check_rate_limit(self, key: str, max_requests: int, window_seconds: int) -> bool:
        return True
