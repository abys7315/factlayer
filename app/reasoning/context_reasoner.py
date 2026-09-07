"""Context reasoner — determines which context dimensions differ."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ContextDifferenceResult:
    """Result of context difference analysis."""
    primary_difference: str  # period, scope, geography, basis, unit
    differing_dimensions: list[str] = field(default_factory=list)
    confidence: float = 0.9
    explanation: str = ""


class ContextReasoner:
    """
    Determines CONTEXTUAL_DIFFERENCE by analyzing which context dimensions differ.
    Produces explanations for the "Why not contradiction?" UI feature.
    """

    def check_context_difference(
        self,
        fact_a,
        fact_b,
        same_period: bool,
        same_scope: bool,
        same_geography: bool,
        same_basis: bool,
        same_unit: bool,
    ) -> ContextDifferenceResult | None:
        """Check if context dimensions differ. Returns None if all match."""
        differences: list[tuple[str, str, str, str]] = []  # (dimension, val_a, val_b, explanation)

        if not same_period:
            period_a = self._format_period(fact_a)
            period_b = self._format_period(fact_b)
            differences.append((
                "period", period_a, period_b,
                f"Facts cover different temporal scopes. "
                f"A covers {period_a}; B covers {period_b}.",
            ))

        if not same_scope:
            scope_a = fact_a.scope or "unspecified"
            scope_b = fact_b.scope or "unspecified"
            differences.append((
                "scope", scope_a, scope_b,
                f"Facts have different reporting scopes. "
                f"A is {scope_a}; B is {scope_b}.",
            ))

        if not same_geography:
            geo_a = fact_a.geography or "unspecified"
            geo_b = fact_b.geography or "unspecified"
            differences.append((
                "geography", geo_a, geo_b,
                f"Facts cover different geographic regions. "
                f"A is {geo_a}; B is {geo_b}.",
            ))

        if not same_basis:
            basis_a = fact_a.basis or "unspecified"
            basis_b = fact_b.basis or "unspecified"
            differences.append((
                "basis", basis_a, basis_b,
                f"Facts use different accounting bases. "
                f"A is {basis_a}; B is {basis_b}.",
            ))

        if not same_unit:
            unit_a = fact_a.unit or "unspecified"
            unit_b = fact_b.unit or "unspecified"
            differences.append((
                "unit", unit_a, unit_b,
                f"Facts use different units. "
                f"A is {unit_a}; B is {unit_b}.",
            ))

        if not differences:
            return None

        primary = differences[0]
        return ContextDifferenceResult(
            primary_difference=primary[0],
            differing_dimensions=[d[0] for d in differences],
            confidence=min(0.95, 0.8 + len(differences) * 0.05),
            explanation="; ".join(d[3] for d in differences),
        )

    def _format_period(self, fact) -> str:
        """Format a fact's period for display."""
        parts = []
        if fact.fiscal_year:
            parts.append(fact.fiscal_year)
        if fact.fiscal_quarter:
            parts.append(fact.fiscal_quarter)
        if fact.reporting_period_label:
            parts.append(f"({fact.reporting_period_label})")
        return " ".join(parts) if parts else "unspecified"
