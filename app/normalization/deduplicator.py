"""Fact deduplication — merges evidence onto canonical facts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeduplicationResult:
    """Result of deduplication check."""
    is_duplicate: bool
    canonical_fact_id: str | None = None
    merge_reason: str = ""


class FactDeduplicator:
    """
    Prevents duplicate facts when multiple blocks express the same claim.
    Merges evidence onto the canonical fact when appropriate.
    """

    def __init__(self):
        # In-memory fingerprint index: fingerprint → (fact_id, object_value, quality)
        self._fingerprint_index: dict[str, list[tuple[str, str, str]]] = {}

    def register_fact(self, fact_id: str, fingerprint: str, object_value: str, quality: str):
        """Register a fact in the deduplication index."""
        if fingerprint not in self._fingerprint_index:
            self._fingerprint_index[fingerprint] = []
        self._fingerprint_index[fingerprint].append((fact_id, object_value, quality))

    def check_duplicate(
        self, fingerprint: str, object_value: str, tolerance: float = 0.005
    ) -> DeduplicationResult:
        """
        Check if a fact with the same fingerprint and similar value already exists.
        If so, return the canonical fact ID for evidence merging.
        """
        if fingerprint not in self._fingerprint_index:
            return DeduplicationResult(is_duplicate=False)

        existing = self._fingerprint_index[fingerprint]
        for existing_id, existing_value, existing_quality in existing:
            if self._values_match(object_value, existing_value, tolerance):
                return DeduplicationResult(
                    is_duplicate=True,
                    canonical_fact_id=existing_id,
                    merge_reason=f"Same fingerprint '{fingerprint}', matching value '{object_value}' ≈ '{existing_value}'",
                )

        return DeduplicationResult(is_duplicate=False)

    def _values_match(self, val_a: str, val_b: str, tolerance: float) -> bool:
        """Check if two values match (exact for text, within tolerance for numbers)."""
        # Exact string match
        if val_a.strip().lower() == val_b.strip().lower():
            return True

        # Try numeric comparison
        try:
            num_a = float(val_a.replace(",", "").replace("$", "").replace("€", "").replace("£", ""))
            num_b = float(val_b.replace(",", "").replace("$", "").replace("€", "").replace("£", ""))
            if num_a == 0 and num_b == 0:
                return True
            if max(abs(num_a), abs(num_b)) == 0:
                return False
            relative_diff = abs(num_a - num_b) / max(abs(num_a), abs(num_b))
            return relative_diff <= tolerance
        except (ValueError, TypeError):
            return False

    def clear(self):
        """Clear the deduplication index."""
        self._fingerprint_index.clear()
