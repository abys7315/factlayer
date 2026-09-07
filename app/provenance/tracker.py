"""Provenance quality tracker."""

from __future__ import annotations

from typing import Any
from app.models.enums import ProvenanceQuality


class ProvenanceTracker:
    """Assigns provenance quality scores to facts based on evidence quality."""

    def normalize_bbox(
        self, raw_bbox: dict[str, float] | list[float], page_width: float, page_height: float
    ) -> dict[str, float]:
        """Normalize bounding box coordinates to [0.0, 1.0] range."""
        if isinstance(raw_bbox, list) and len(raw_bbox) == 4:
            x0, y0, x1, y1 = raw_bbox
        elif isinstance(raw_bbox, dict):
            x0 = raw_bbox.get("x0", 0.0)
            y0 = raw_bbox.get("y0", 0.0)
            x1 = raw_bbox.get("x1", 0.0)
            y1 = raw_bbox.get("y1", 0.0)
        else:
            return {"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0}

        w = max(page_width, 1.0)
        h = max(page_height, 1.0)

        return {
            "x0": max(0.0, min(1.0, x0 / w)),
            "y0": max(0.0, min(1.0, y0 / h)),
            "x1": max(0.0, min(1.0, x1 / w)),
            "y1": max(0.0, min(1.0, y1 / h)),
        }

    def compute_quality(
        self,
        validation_method: str | None,
        validation_score: float | None,
        source_type: str,
        ocr_applied: bool,
        has_bbox: bool,
        has_block_id: bool,
    ) -> str:
        """
        Compute provenance quality level.

        HIGH: exact match, page + bbox + block, structured text/table
        MEDIUM: fuzzy match, page confirmed, or clear chart
        LOW: ambiguous chart, low OCR confidence, heavy inference
        """
        score = 0.0

        # Validation method contribution
        if validation_method == "exact_match":
            score += 0.4
        elif validation_method == "normalized_match":
            score += 0.35
        elif validation_method == "fuzzy_match":
            score += 0.2
        elif validation_method == "ocr_fuzzy":
            score += 0.15
        else:
            score += 0.0

        # Validation score contribution
        if validation_score:
            score += validation_score * 0.2

        # Source type contribution
        source_scores = {
            "text": 0.2,
            "table_cell": 0.2,
            "heading": 0.15,
            "footnote": 0.15,
            "caption": 0.1,
            "figure": 0.05,
            "chart": 0.05,
        }
        score += source_scores.get(source_type, 0.1)

        # Location quality
        if has_bbox:
            score += 0.1
        if has_block_id:
            score += 0.1

        # OCR penalty
        if ocr_applied:
            score -= 0.1

        # Map to level
        if score >= 0.7:
            return ProvenanceQuality.HIGH.value
        elif score >= 0.4:
            return ProvenanceQuality.MEDIUM.value
        else:
            return ProvenanceQuality.LOW.value
