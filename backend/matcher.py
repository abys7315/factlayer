"""Fact Matcher — cross-document semantic similarity search and candidate pair generation."""

from __future__ import annotations
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
from backend.db import Fact
from backend.embeddings import EmbeddingGenerator, embed_fact, embed_facts_batch


def find_candidate_pairs(
    facts: List[Dict[str, Any]],
    threshold: float = 0.55,
    top_k: Optional[int] = None,
) -> List[Tuple[Dict[str, Any], Dict[str, Any], float]]:
    """
    Candidate matching using free local cosine similarity to narrow thousands of facts
    down to high-probability pairs worth reasoning about, before any LLM calls.
    
    Returns:
        List of (fact_a, fact_b, similarity_score) tuples sorted descending by similarity.
    """
    if len(facts) < 2:
        return []

    # Ensure all facts have embeddings
    fact_texts = [f.get("fact_text", "") for f in facts]
    embeddings = []
    missing_indices = []
    
    for i, f in enumerate(facts):
        emb = f.get("embedding")
        if emb and isinstance(emb, list) and len(emb) == 384:
            embeddings.append(emb)
        else:
            embeddings.append(None)
            missing_indices.append(i)

    if missing_indices:
        missing_texts = [fact_texts[idx] for idx in missing_indices]
        computed_embs = embed_facts_batch(missing_texts)
        for idx, emb in zip(missing_indices, computed_embs):
            embeddings[idx] = emb
            facts[idx]["embedding"] = emb

    candidate_pairs = []
    n = len(facts)
    for i in range(n):
        emb_a = embeddings[i]
        if not emb_a:
            continue
        for j in range(i + 1, n):
            emb_b = embeddings[j]
            if not emb_b:
                continue

            sim = EmbeddingGenerator.cosine_similarity(emb_a, emb_b)
            if sim >= threshold:
                candidate_pairs.append((facts[i], facts[j], float(sim)))

    # Sort descending by cosine similarity
    candidate_pairs.sort(key=lambda x: x[2], reverse=True)
    if top_k is not None:
        return candidate_pairs[:top_k]
    return candidate_pairs


class FactMatcher:
    """Finds top-K semantically similar candidate facts across documents."""

    def __init__(self, top_k: int = 5, similarity_threshold: float = 0.55):
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold

    def find_matches(
        self,
        target_fact: Fact,
        all_facts: List[Fact],
        exclude_same_doc: bool = False,
    ) -> List[Tuple[Fact, float]]:
        """
        Compare target_fact against all_facts using cosine similarity.
        
        Returns:
            List of (Fact, similarity_score) sorted by descending similarity.
        """
        target_emb = target_fact.get_embedding()
        if not target_emb:
            return []

        candidates = []
        for other in all_facts:
            # Skip comparing against self
            if other.id == target_fact.id:
                continue

            if exclude_same_doc and other.doc_id == target_fact.doc_id:
                continue

            other_emb = other.get_embedding()
            if not other_emb:
                continue

            sim = EmbeddingGenerator.cosine_similarity(target_emb, other_emb)
            if sim >= self.similarity_threshold:
                candidates.append((other, sim))

        # Sort descending by similarity
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:self.top_k]
