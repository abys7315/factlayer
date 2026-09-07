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

        # Strategy 3: Vector similarity (Qdrant)
        if embedding:
            vector_results = await self.qdrant.search_similar_facts(
                query_embedding=embedding,
                limit=self.MAX_CANDIDATES_PER_FACT,
                score_threshold=0.7,
                exclude_document_id=exclude_document_id,
            )
            for vr in vector_results:
                other_id = vr["fact_id"]
                if other_id == fact_id_str:
                    continue
                if other_id not in candidates:
                    candidates[other_id] = RetrievalCandidate(
                        fact_id=other_id, score=vr["score"] * 0.8,
                        method="vector", payload=vr.get("payload", {}),
                    )
                else:
                    # Boost existing candidates found by vector search too
                    candidates[other_id].score = min(1.0, candidates[other_id].score + 0.1)

        # Sort by score and limit
        sorted_candidates = sorted(candidates.values(), key=lambda c: c.score, reverse=True)
        return sorted_candidates[:self.MAX_CANDIDATES_PER_FACT]
