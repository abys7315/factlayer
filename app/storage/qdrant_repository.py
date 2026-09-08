"""Qdrant vector storage and semantic search with fallback in-memory cache."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance, VectorParams, PointStruct,
        Filter, FieldCondition, MatchValue,
    )
except ImportError:
    QdrantClient = None
    Distance = VectorParams = PointStruct = Filter = FieldCondition = MatchValue = None

from app.config import get_settings


class QdrantRepository:
    """Vector storage for semantic similarity search on facts."""

    def __init__(self):
        self.settings = get_settings()
        self._client: Any = None
        self._collection = self.settings.QDRANT_COLLECTION
        self._memory_points: dict[str, dict[str, Any]] = {}

    def _get_client(self):
        if QdrantClient is None:
            return None
        if self._client is None:
            try:
                self._client = QdrantClient(url=self.settings.QDRANT_URL, timeout=2.0)
            except Exception:
                self._client = None
        return self._client

    async def ensure_collection(self):
        """Create collection if it doesn't exist."""
        client = self._get_client()
        if client is None:
            return
        try:
            collections = client.get_collections().collections
            names = [c.name for c in collections]
            if self._collection not in names:
                client.create_collection(
                    collection_name=self._collection,
                    vectors_config=VectorParams(
                        size=self.settings.EMBEDDING_DIMENSIONS,
                        distance=Distance.COSINE,
                    ),
                )
        except Exception:
            pass

    async def upsert_fact_embedding(
        self,
        fact_id: str,
        embedding: list[float],
        payload: dict[str, Any],
    ):
        """Upsert fact embedding with metadata payload in Qdrant and memory cache."""
        self._memory_points[fact_id] = {"vector": embedding, "payload": payload}
        client = self._get_client()
        if client is not None and PointStruct is not None:
            try:
                client.upsert(
                    collection_name=self._collection,
                    points=[
                        PointStruct(
                            id=str(uuid.UUID(fact_id)) if isinstance(fact_id, str) and len(fact_id) == 36 else str(uuid.uuid4()),
                            vector=embedding,
                            payload=payload,
                        )
                    ],
                )
            except Exception:
                pass

    async def search_similar_facts(
        self,
        query_embedding: list[float],
        entity_name: str | None = None,
        category: str | None = None,
        limit: int = 10,
        score_threshold: float = 0.55,
        exclude_document_id: str | None = None,
        **kwargs,
    ) -> list[dict[str, Any]]:
        """Find facts semantically similar to the query using real cosine similarity."""
        client = self._get_client()
        if client is not None:
            try:
                results = client.search(
                    collection_name=self._collection,
                    query_vector=query_embedding,
                    limit=limit * 2 if exclude_document_id else limit,
                    score_threshold=score_threshold,
                )
                out = []
                for r in results:
                    payload = r.payload or {}
                    if exclude_document_id and payload.get("document_id") == exclude_document_id:
                        continue
                    out.append({
                        "id": str(r.id),
                        "fact_id": str(r.id),
                        "score": r.score,
                        "payload": payload,
                    })
                    if len(out) >= limit:
                        break
                if out:
                    return out
            except Exception:
                pass

        # Real in-memory dense cosine similarity search
        import numpy as np
        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = float(np.linalg.norm(q_vec))

        scored_candidates = []
        for fid, pt in self._memory_points.items():
            payload = pt.get("payload", {})
            if exclude_document_id and payload.get("document_id") == exclude_document_id:
                continue

            v = pt.get("vector", [])
            if not v:
                continue

            p_vec = np.array(v, dtype=np.float32)
            p_norm = float(np.linalg.norm(p_vec))

            if q_norm > 0 and p_norm > 0:
                sim = float(np.dot(q_vec, p_vec) / (q_norm * p_norm))
            else:
                sim = 0.0

            if sim >= score_threshold:
                scored_candidates.append({
                    "id": fid,
                    "fact_id": fid,
                    "score": round(sim, 4),
                    "payload": payload,
                })

        scored_candidates.sort(key=lambda x: x["score"], reverse=True)
        return scored_candidates[:limit]

