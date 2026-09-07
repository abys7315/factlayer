"""Provenance validator — ensures complete evidence chains."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GroundingResult:
    """Result of snippet grounding check."""
    is_grounded: bool
    char_offset_start: int = -1
    char_offset_end: int = -1
    match_score: float = 0.0


@dataclass
class ProvenanceCheck:
    """Result of provenance validation."""
    is_valid: bool
    issues: list[str]


class ProvenanceValidator:
    """Validates complete provenance chains for facts and relationships."""

    def validate_grounding(self, page_text: str, snippet: str) -> GroundingResult:
        """Verify that snippet exists within page text and extract character offsets."""
        if not snippet or not page_text:
            return GroundingResult(is_grounded=False)

        idx = page_text.lower().find(snippet.lower())
        if idx != -1:
            return GroundingResult(
                is_grounded=True,
                char_offset_start=idx,
                char_offset_end=idx + len(snippet),
                match_score=1.0,
            )

        # Fallback substring match
        return GroundingResult(is_grounded=False)

    def validate_fact_provenance(self, fact, evidence_list) -> ProvenanceCheck:
        """Validate that a fact has proper provenance."""
        issues = []

        if not evidence_list:
            issues.append("Fact has no evidence records")

        for ev in evidence_list:
            if not getattr(ev, 'is_validated', True):
                issues.append(f"Evidence {ev.id} has not been validated")
            if not getattr(ev, 'excerpt', None) and not getattr(ev, 'snippet', None):
                issues.append(f"Evidence {ev.id} has no excerpt text")
            if getattr(ev, 'page_number', 1) <= 0:
                issues.append(f"Evidence {ev.id} has invalid page number")

        return ProvenanceCheck(is_valid=len(issues) == 0, issues=issues)

    def validate_relationship_provenance(
        self, relationship, fact_a_evidence, fact_b_evidence
    ) -> ProvenanceCheck:
        """Validate that a relationship has evidence from both sides."""
        issues = []

        if not fact_a_evidence:
            issues.append("No evidence available for Fact A")
        if not fact_b_evidence:
            issues.append("No evidence available for Fact B")

        if not getattr(relationship, 'reasoning_trace', None):
            issues.append("Relationship has no reasoning trace")

        if not getattr(relationship, 'explanation', None):
            issues.append("Relationship has no explanation")

        if getattr(relationship, 'confidence', 1.0) <= 0:
            issues.append("Relationship has zero confidence")

        return ProvenanceCheck(is_valid=len(issues) == 0, issues=issues)
