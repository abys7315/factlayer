"""Deterministic comparison engine with configurable tolerances and temporal reasoning."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.config import get_settings
from app.models.enums import RelationshipType
from app.reasoning.temporal_reasoner import TemporalReasoner
from app.reasoning.context_reasoner import ContextReasoner


@dataclass
class ComparisonResult:
    """Result of comparing two facts."""
    relationship_type: str
    confidence: float
    classification_method: str = "deterministic"
    reasoning_trace: dict = field(default_factory=dict)
    explanation: str = ""
    context_difference_type: str | None = None
    supersession_date: date | None = None
    is_ambiguous: bool = False


class ComparisonEngine:
    """
    Deterministic comparison engine handling clear cases without LLM.
    Delegates ambiguous cases to LLM reasoner.
    """

    def __init__(self):
        self.settings = get_settings()
        self.temporal = TemporalReasoner()
        self.context = ContextReasoner()

    def compare(self, fact_a, fact_b) -> ComparisonResult:
        """
        Compare two facts and determine their relationship.
        Returns ComparisonResult with structured reasoning trace.
        """
        trace: dict[str, Any] = {}

        # Step 1: Context alignment check
        same_entity = self._check_same_entity(fact_a, fact_b)
        same_predicate = self._check_same_predicate(fact_a, fact_b)
        same_period = self._check_same_period(fact_a, fact_b)
        same_scope = self._check_same_scope(fact_a, fact_b)
        same_unit = self._check_same_unit(fact_a, fact_b)
        same_geography = self._check_same_geography(fact_a, fact_b)
        same_basis = self._check_same_basis(fact_a, fact_b)

        trace["same_entity"] = same_entity
        trace["same_predicate"] = same_predicate
        trace["same_period"] = same_period
        trace["same_scope"] = same_scope
        trace["same_unit"] = same_unit
        trace["same_geography"] = same_geography
        trace["same_basis"] = same_basis

        # If entities or predicates don't match → UNRELATED
        if not same_entity or not same_predicate:
            return ComparisonResult(
                relationship_type=RelationshipType.UNRELATED.value,
                confidence=0.95,
                reasoning_trace=trace,
                explanation=f"{'Different entities' if not same_entity else 'Different predicates'}",
            )

        # Step 2: Check for contextual differences
        ctx_result = self.context.check_context_difference(
            fact_a, fact_b, same_period, same_scope, same_geography, same_basis, same_unit
        )
        if ctx_result:
            trace["differing_dimensions"] = ctx_result.differing_dimensions
            return ComparisonResult(
                relationship_type=RelationshipType.CONTEXTUAL_DIFFERENCE.value,
                confidence=ctx_result.confidence,
                reasoning_trace=trace,
                explanation=ctx_result.explanation,
                context_difference_type=ctx_result.primary_difference,
            )

        # Step 3: Compare values
        trace["value_a"] = fact_a.object_value
        trace["value_b"] = fact_b.object_value

        if fact_a.object_numeric is not None and fact_b.object_numeric is not None:
            # Numeric comparison with tolerances
            result = self._compare_numeric(
                fact_a.object_numeric, fact_b.object_numeric,
                fact_a.unit, trace,
            )
        else:
            # Categorical/text comparison
            result = self._compare_categorical(
                fact_a.object_value, fact_b.object_value, trace,
            )

        # Step 4: Check for supersession (temporal ordering)
        if result.relationship_type == RelationshipType.CONTRADICTS.value:
            supersession = self.temporal.check_supersession(fact_a, fact_b)
            if supersession:
                trace["temporal_order"] = supersession.temporal_order
                return ComparisonResult(
                    relationship_type=RelationshipType.SUPERSEDES.value,
                    confidence=supersession.confidence,
                    reasoning_trace=trace,
                    explanation=supersession.explanation,
                    supersession_date=supersession.supersession_date,
                )

        result.reasoning_trace = trace
        return result

    def _check_same_entity(self, a, b) -> bool:
        if a.entity_id and b.entity_id:
            return a.entity_id == b.entity_id
        return a.subject.lower().strip() == b.subject.lower().strip()

    def _check_same_predicate(self, a, b) -> bool:
        return a.predicate.lower().strip() == b.predicate.lower().strip()

    def _check_same_period(self, a, b) -> bool:
        if a.fiscal_year and b.fiscal_year:
            if a.fiscal_year != b.fiscal_year:
                return False
            if a.fiscal_quarter and b.fiscal_quarter:
                return a.fiscal_quarter == b.fiscal_quarter
            # One has quarter, other doesn't → not same period
            if bool(a.fiscal_quarter) != bool(b.fiscal_quarter):
                return False
        return True

    def _check_same_scope(self, a, b) -> bool:
        if a.scope and b.scope:
            return a.scope.lower().strip() == b.scope.lower().strip()
        return True  # If either is unspecified, assume compatible

    def _check_same_unit(self, a, b) -> bool:
        if a.unit and b.unit:
            return a.unit.lower().strip() == b.unit.lower().strip()
        return True

    def _check_same_geography(self, a, b) -> bool:
        if a.geography and b.geography:
            return a.geography.lower().strip() == b.geography.lower().strip()
        return True

    def _check_same_basis(self, a, b) -> bool:
        if a.basis and b.basis:
            return a.basis.lower().strip() == b.basis.lower().strip()
        return True

    def _compare_numeric(
        self, val_a: float, val_b: float, unit: str | None, trace: dict
    ) -> ComparisonResult:
        """Compare numeric values with configurable tolerances."""
        if val_a == 0 and val_b == 0:
            trace["relative_difference"] = 0.0
            return ComparisonResult(
                relationship_type=RelationshipType.CORROBORATES.value,
                confidence=1.0,
                explanation="Both values are zero",
            )

        denominator = max(abs(val_a), abs(val_b))
        if denominator == 0:
            denominator = 1

        rel_diff = abs(val_a - val_b) / denominator
        trace["relative_difference"] = round(rel_diff, 6)

        # Get tolerance based on unit type
        eq_tol = self.settings.NUMERIC_TOLERANCE_EQUIVALENT
        round_tol = self.settings.NUMERIC_TOLERANCE_ROUNDING
        contra_tol = self.settings.NUMERIC_TOLERANCE_CONTRADICTION

        # Percentage metrics use absolute difference instead
        if unit and unit == "%":
            abs_diff = abs(val_a - val_b)
            trace["absolute_difference"] = round(abs_diff, 4)
            if abs_diff <= 0.1:
                trace["tolerance_applied"] = "percentage_equivalent"
                return ComparisonResult(
                    relationship_type=RelationshipType.CORROBORATES.value,
                    confidence=0.95,
                    explanation=f"Values {val_a}% and {val_b}% differ by {abs_diff:.2f} percentage points (within tolerance)",
                )
            elif abs_diff <= 1.0:
                trace["tolerance_applied"] = "percentage_rounding"
                return ComparisonResult(
                    relationship_type=RelationshipType.CORROBORATES.value,
                    confidence=0.8,
                    explanation=f"Values {val_a}% and {val_b}% differ by {abs_diff:.2f} percentage points (possible rounding)",
                )
            else:
                trace["tolerance_applied"] = "percentage_contradiction"
                return ComparisonResult(
                    relationship_type=RelationshipType.CONTRADICTS.value,
                    confidence=min(0.95, 0.7 + abs_diff / 20),
                    explanation=f"Values {val_a}% and {val_b}% differ by {abs_diff:.2f} percentage points",
                )

        # Standard numeric comparison
        trace["tolerance_applied"] = "numeric"
        if rel_diff <= eq_tol:
            return ComparisonResult(
                relationship_type=RelationshipType.CORROBORATES.value,
                confidence=0.95,
                explanation=f"Values differ by {rel_diff*100:.2f}% (within equivalent tolerance of {eq_tol*100:.1f}%)",
            )
        elif rel_diff <= round_tol:
            return ComparisonResult(
                relationship_type=RelationshipType.CORROBORATES.value,
                confidence=0.75,
                explanation=f"Values differ by {rel_diff*100:.2f}% (possible rounding within {round_tol*100:.1f}% tolerance)",
            )
        else:
            return ComparisonResult(
                relationship_type=RelationshipType.CONTRADICTS.value,
                confidence=min(0.95, 0.7 + rel_diff),
                explanation=f"Values differ by {rel_diff*100:.2f}% (exceeds {contra_tol*100:.1f}% tolerance)",
            )

    def _compare_categorical(
        self, val_a: str, val_b: str, trace: dict
    ) -> ComparisonResult:
        """Compare non-numeric values."""
        norm_a = val_a.strip().lower()
        norm_b = val_b.strip().lower()

        if norm_a == norm_b:
            return ComparisonResult(
                relationship_type=RelationshipType.CORROBORATES.value,
                confidence=0.95,
                explanation=f"Identical values: '{val_a}'",
            )

        # Different categorical values — could be contradiction or supersession
        return ComparisonResult(
            relationship_type=RelationshipType.CONTRADICTS.value,
            confidence=0.7,
            explanation=f"Different values: '{val_a}' vs '{val_b}'",
            is_ambiguous=True,  # Flag for LLM review
        )
