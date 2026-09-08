"""Real-time Server-Sent Events (SSE) stream for live updates."""

from __future__ import annotations

import asyncio
import json
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.database import get_session_factory
from app.storage.postgres_repository import PostgresRepository

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/events/stream")
async def event_stream():
    """
    Server-Sent Events endpoint streaming real-time statistics,
    live processing updates, and cross-document relationship events.
    """
    async def event_generator():
        session_factory = get_session_factory()
        last_rel_count = None
        last_fact_count = None

        while True:
            try:
                async with session_factory() as session:
                    repo = PostgresRepository(session)
                    docs = await repo.list_documents(limit=10)
                    total_facts = await repo.count_facts()
                    total_rels = await repo.count_relationships()
                    corroborations = await repo.count_relationships("CORROBORATES")
                    contradictions = await repo.count_relationships("CONTRADICTS")
                    contextual = await repo.count_relationships("CONTEXTUAL_DIFFERENCE")
                    superseded = await repo.count_relationships("SUPERSEDES")

                    processing_docs = [
                        {
                            "id": str(d.id),
                            "filename": d.filename,
                            "stage": d.current_stage or d.status or "PROCESSING",
                            "status": d.status,
                        }
                        for d in docs if d.status not in ("COMPLETED", "FAILED")
                    ]

                    has_new = (last_rel_count is not None and total_rels != last_rel_count) or (
                        last_fact_count is not None and total_facts != last_fact_count
                    )

                    payload = {
                        "total_facts": total_facts,
                        "total_relationships": total_rels,
                        "corroborations": corroborations,
                        "contradictions": contradictions,
                        "contextual_differences": contextual,
                        "superseded": superseded,
                        "processing_docs": processing_docs,
                        "has_new_relationships": has_new,
                        "timestamp": asyncio.get_event_loop().time(),
                    }

                    last_rel_count = total_rels
                    last_fact_count = total_facts

                    yield f"data: {json.dumps(payload)}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

            await asyncio.sleep(2.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
