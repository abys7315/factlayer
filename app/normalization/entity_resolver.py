"""Multi-stage entity resolution with safety controls."""

from __future__ import annotations

import re
import difflib
from dataclasses import dataclass

try:
    from rapidfuzz import fuzz
except ImportError:
    class FuzzFallback:
        @staticmethod
        def ratio(s1: str, s2: str) -> float:
            return difflib.SequenceMatcher(None, s1, s2).ratio() * 100.0
    fuzz = FuzzFallback()

from app.models.enums import EntityMatchConfidence


@dataclass
class ResolutionResult:
    """Result of entity resolution."""
    match_type: str  # MATCH, POSSIBLE_MATCH, NO_MATCH
    entity_id: str | None = None
    canonical_name: str | None = None
    confidence: float = 0.0
    method: str = ""  # exact_alias, normalized, metadata, embedding, llm
    reasoning: str = ""


class EntityResolver:
    """
    Multi-stage entity resolution with safety controls.
    Never auto-merges entities with confidence < 0.95.
    """

    # Common suffixes to strip for comparison
    SUFFIXES = [
        " Inc.", " Inc", " Corp.", " Corp", " Corporation",
        " Ltd.", " Ltd", " Limited", " LLC", " LLP",
        " PLC", " plc", " Group", " Holdings", " Co.", " Co",
        " & Co", " & Co.", " S.A.", " SA", " AG", " GmbH",
        " NV", " N.V.", " SE",
    ]

    def __init__(self):
        self._alias_cache: dict[str, tuple[str, str]] = {}  # alias → (entity_id, canonical)

    def register_alias(self, alias: str, entity_id: str, canonical_name: str):
        """Register a known alias for an entity."""
        self._alias_cache[alias.lower().strip()] = (entity_id, canonical_name)
        self._alias_cache[self._normalize_name(alias)] = (entity_id, canonical_name)

    def resolve(
        self,
        name: str,
        context: dict | None = None,
    ) -> ResolutionResult:
        """
        Resolve an entity name through multiple stages.
        Returns the best match with confidence.
        """
        name = name.strip()
        if not name:
            return ResolutionResult(match_type="NO_MATCH", confidence=0.0)

        # Stage 1: Exact alias matching
        result = self._exact_alias_match(name)
        if result and result.confidence >= 0.95:
            return result

        # Stage 2: Normalized string matching
        result = self._normalized_match(name)
        if result and result.confidence >= 0.90:
            return result

        # Stage 3: Metadata/context matching (if context provided)
        if context:
            result = self._metadata_match(name, context)
            if result and result.confidence >= 0.85:
                return result

        # Stage 4: Fuzzy matching against known aliases
        result = self._fuzzy_match(name)
        if result:
            return result

        # No match found
        return ResolutionResult(
            match_type="NO_MATCH",
            confidence=0.0,
            method="none",
            reasoning=f"No match found for '{name}' in known entities",
        )

    def resolve_entity_name(self, name: str) -> str:
        """Convenience method returning canonical name or normalized form."""
        res = self.resolve(name)
        return res.canonical_name or self._normalize_name(name)

    def are_same_entity(self, name1: str, name2: str) -> bool:
        """Check if two entity names refer to the same entity."""
        norm1 = self._normalize_name(name1)
        norm2 = self._normalize_name(name2)
        if norm1 == norm2:
            return True
        sim = fuzz.ratio(norm1, norm2)
        return sim >= 85.0

    def normalize_entity_string(self, name: str) -> str:
        return self._normalize_name(name)

    def _exact_alias_match(self, name: str) -> ResolutionResult | None:
        """Stage 1: Exact alias lookup."""
        key = name.lower().strip()
        if key in self._alias_cache:
            entity_id, canonical = self._alias_cache[key]
            return ResolutionResult(
                match_type="MATCH",
                entity_id=entity_id,
                canonical_name=canonical,
                confidence=1.0,
                method="exact_alias",
                reasoning=f"Exact alias match: '{name}' → '{canonical}'",
            )
        return None

    def _normalized_match(self, name: str) -> ResolutionResult | None:
        """Stage 2: Normalized name matching (strip suffixes, lowercase)."""
        normalized = self._normalize_name(name)
        if normalized in self._alias_cache:
            entity_id, canonical = self._alias_cache[normalized]
            return ResolutionResult(
                match_type="MATCH",
                entity_id=entity_id,
                canonical_name=canonical,
                confidence=0.95,
                method="normalized",
                reasoning=f"Normalized match: '{name}' → '{normalized}' → '{canonical}'",
            )
        return None

    def _metadata_match(self, name: str, context: dict) -> ResolutionResult | None:
        """Stage 3: Match using context metadata (industry, country, etc.)."""
        normalized = self._normalize_name(name)
        best_score = 0.0
        best_match = None

        for alias_key, (entity_id, canonical) in self._alias_cache.items():
            name_sim = fuzz.ratio(normalized, alias_key) / 100.0
            if name_sim > 0.7:
                score = name_sim * 0.9 + 0.1
                if score > best_score:
                    best_score = score
                    best_match = (entity_id, canonical)

        if best_match and best_score >= 0.85:
            return ResolutionResult(
                match_type="POSSIBLE_MATCH",
                entity_id=best_match[0],
                canonical_name=best_match[1],
                confidence=best_score,
                method="metadata",
                reasoning=f"Metadata-assisted match: '{name}' → '{best_match[1]}' (score: {best_score:.2f})",
            )
        return None

    def _fuzzy_match(self, name: str) -> ResolutionResult | None:
        """Stage 4: Fuzzy string matching against known aliases."""
        normalized = self._normalize_name(name)
        best_score = 0.0
        best_match = None

        for alias_key, (entity_id, canonical) in self._alias_cache.items():
            score = fuzz.ratio(normalized, alias_key) / 100.0
            if score > best_score:
                best_score = score
                best_match = (entity_id, canonical, alias_key)

        if best_match:
            if best_score >= 0.92:
                return ResolutionResult(
                    match_type="POSSIBLE_MATCH",
                    entity_id=best_match[0],
                    canonical_name=best_match[1],
                    confidence=best_score,
                    method="fuzzy",
                    reasoning=f"Fuzzy match: '{name}' ≈ '{best_match[2]}' → '{best_match[1]}' (score: {best_score:.2f})",
                )
            elif best_score >= 0.7:
                return ResolutionResult(
                    match_type="POSSIBLE_MATCH",
                    entity_id=best_match[0],
                    canonical_name=best_match[1],
                    confidence=best_score,
                    method="fuzzy",
                    reasoning=f"Low-confidence fuzzy match: '{name}' ≈ '{best_match[1]}' (score: {best_score:.2f}). Manual review recommended.",
                )
        return None

    def _normalize_name(self, name: str) -> str:
        """Normalize entity name for comparison."""
        cleaned = name.strip()
        for suffix in self.SUFFIXES:
            if cleaned.endswith(suffix):
                cleaned = cleaned[:-len(suffix)].strip()
                break
        cleaned = re.sub(r'[^\w\s]', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned.lower().strip())
        return cleaned
