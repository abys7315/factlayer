"""Sentence-transformers wrapper for local fact embeddings with NumPy fallback.

Provides embed_fact and embed_facts_batch using local sentence-transformers models.
"""

from __future__ import annotations
import math
import hashlib
import logging
from typing import List, Union
import numpy as np

logger = logging.getLogger(__name__)

_GLOBAL_EMBEDDER = None


def get_embedder() -> EmbeddingGenerator:
    """Singleton getter for EmbeddingGenerator."""
    global _GLOBAL_EMBEDDER
    if _GLOBAL_EMBEDDER is None:
        _GLOBAL_EMBEDDER = EmbeddingGenerator()
    return _GLOBAL_EMBEDDER


def embed_fact(fact: str) -> List[float]:
    """Turn a fact string into a normalized 384-dimensional vector."""
    return get_embedder().generate_embedding(fact)


def embed_facts_batch(facts: List[str]) -> List[List[float]]:
    """Batch compute embeddings for multiple fact strings."""
    embedder = get_embedder()
    if embedder.model is not None and facts:
        try:
            embs = embedder.model.encode(facts, convert_to_numpy=True, normalize_embeddings=True)
            return embs.tolist()
        except Exception as e:
            logger.warning(f"Batch embedding failed: {e}. Falling back to sequential.")
    return [embedder.generate_embedding(f) for f in facts]


class EmbeddingGenerator:
    """Generates local dense vector embeddings for facts."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self._init_model()

    def _init_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Loaded sentence-transformers model: {self.model_name}")
        except Exception as e:
            logger.info(f"SentenceTransformer not loaded ({e}). Using deterministic token-hash embeddings.")
            self.model = None

    def generate_embedding(self, text: str) -> List[float]:
        """Generate normalized 384-dimensional vector embedding for text."""
        if not text or not text.strip():
            return [0.0] * 384

        if self.model is not None:
            try:
                emb = self.model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
                return emb.tolist()
            except Exception as e:
                logger.warning(f"Error in model encoding: {e}. Using fallback.")

        # Deterministic 384-dim semantic feature vector fallback
        return self._hash_embedding(text, dim=384)

    def _hash_embedding(self, text: str, dim: int = 384) -> List[float]:
        """Deterministic TF-IDF style bag-of-words hash embedding."""
        import re
        vec = np.zeros(dim, dtype=np.float32)
        clean_text = text.lower().replace("$", " usd ").replace("%", " percent ").replace("₹", " inr ")
        # Tokenize by word characters and numbers
        tokens = re.findall(r"\b[\w\.\,]+\b", clean_text)
        stopwords = {"the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of", "with", "by", "as", "was", "were", "is", "are", "been", "be"}
        filtered_tokens = [t.strip(".,") for t in tokens if t.strip(".,") and t not in stopwords]
        
        for token in filtered_tokens:
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            idx = h % dim
            weight = 2.5 if any(char.isdigit() for char in token) else 1.0
            vec[idx] += weight

        # Add 2-gram context
        for i in range(len(filtered_tokens) - 1):
            bigram = f"{filtered_tokens[i]}_{filtered_tokens[i+1]}"
            h = int(hashlib.md5(bigram.encode("utf-8")).hexdigest(), 16)
            idx = h % dim
            vec[idx] += 1.5

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    @staticmethod
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        """Compute cosine similarity between two vector embeddings."""
        a = np.array(v1, dtype=np.float32)
        b = np.array(v2, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

