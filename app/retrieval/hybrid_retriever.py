"""Hybrid candidate retrieval — avoids O(N²) all-pairs comparison."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from app.storage.postgres_repository import PostgresRepository
from app.storage.qdrant_repository import QdrantRepository


@dataclass
class RetrievalCandidate:
    """A candidate fact pair for comparison."""
    fact_id: str
    score: float
    method: str  # fingerprint, entity_predicate, vector, lexical
    payload: dict[str, Any] = field(default_factory=dict)


class HybridRetriever:
    """
    Multi-strategy candidate retrieval combining:
    1. Context fingerprint grouping (fastest)
    2. Entity + predicate lookup (PostgreSQL)
    3. Vector similarity (Qdrant)
    """

    MAX_CANDIDATES_PER_FACT = 20

    def __init__(self, pg_repo: PostgresRepository, qdrant_repo: QdrantRepository):
        self.pg = pg_repo
        self.qdrant = qdrant_repo

    async def find_candidates(
        self,
        fact,
        embedding: list[float] | None = None,
        exclude_document_id: str | None = None,
    ) -> list[RetrievalCandidate]:
        """
        Find comparison candidates for a newly ingested fact.
        Combines multiple retrieval strategies.
        """
        candidates: dict[str, RetrievalCandidate] = {}
        fact_id_str = str(fact.id)

        # Strategy 1: Context fingerprint grouping (fastest)
        if fact.context_fingerprint:
            fp_facts = await self.pg.get_facts_by_fingerprint(fact.context_fingerprint)
            for fp_fact in fp_facts:
                other_id = str(fp_fact.id)
                if other_id == fact_id_str:
                    continue
                if exclude_document_id and str(fp_fact.document_id) == exclude_document_id:
                    continue
                candidates[other_id] = RetrievalCandidate(
                    fact_id=other_id, score=1.0, method="fingerprint",
                    payload={"fingerprint": fact.context_fingerprint},
                )

        # Strategy 2: Entity + predicate lookup (PostgreSQL)
        if fact.entity_id:
            ep_facts = await self.pg.get_facts_by_entity_predicate(fact.entity_id, fact.predicate)
            for ep_fact in ep_facts:
                other_id = str(ep_fact.id)
                if other_id == fact_id_str:
                    continue
                if exclude_document_id and str(ep_fact.document_id) == exclude_document_id:
                    continue
                if other_id not in candidates:
                    candidates[other_id] = RetrievalCandidate(
                        fact_id=other_id, score=0.9, method="entity_predicate",
                    )
                else:
                    candidates[other_id].score = max(candidates[other_id].score, 0.9)

        # Strategy 3: Vector similarity (Qdrant & Memory Index)
        if embedding:
            vector_results = await self.qdrant.search_similar_facts(
                query_embedding=embedding,
                limit=self.MAX_CANDIDATES_PER_FACT,
                score_threshold=0.55,
                exclude_document_id=exclude_document_id,
            )
            for vr in vector_results:
                other_id = vr["fact_id"]
                if other_id == fact_id_str:
                    continue
                if other_id not in candidates:
                    candidates[other_id] = RetrievalCandidate(
                        fact_id=other_id, score=vr["score"] * 0.9,
                        method="vector", payload=vr.get("payload", {}),
                    )
                else:
                    candidates[other_id].score = min(1.0, candidates[other_id].score + 0.15)

        # Strategy 4: DB-wide cross-document semantic fallback if candidates are few
        if len(candidates) < 5 and embedding:
            all_db_facts = await self.pg.get_all_facts(limit=200)
            from backend.embeddings import EmbeddingGenerator
            for dbf in all_db_facts:
                other_id = str(dbf.id)
                if other_id == fact_id_str:
                    continue
                if exclude_document_id and str(dbf.document_id) == exclude_document_id:
                    continue
                if other_id in candidates:
                    continue

                dbf_text = f"{dbf.subject} {dbf.predicate} {dbf.object_value}"
                dbf_vec = self.qdrant._memory_points.get(other_id, {}).get("vector")
                if not dbf_vec:
                    # Generate and cache embedding
                    try:
                        from backend.embeddings import get_embedder
                        dbf_vec = get_embedder().generate_embedding(dbf_text)
                        self.qdrant._memory_points[other_id] = {"vector": dbf_vec, "payload": {"document_id": str(dbf.document_id)}}
                    except Exception:
                        dbf_vec = None

                if dbf_vec:
                    sim = EmbeddingGenerator.cosine_similarity(embedding[:len(dbf_vec)], dbf_vec[:len(embedding)])
                    if sim >= 0.55:
                        candidates[other_id] = RetrievalCandidate(
                            fact_id=other_id, score=sim * 0.85, method="vector_db",
                        )

        # Sort by score and limit
        sorted_candidates = sorted(candidates.values(), key=lambda c: c.score, reverse=True)
        return sorted_candidates[:self.MAX_CANDIDATES_PER_FACT]

