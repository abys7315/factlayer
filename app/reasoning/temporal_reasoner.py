"""Temporal reasoning — document date vs fact date, supersession detection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class SupersessionResult:
    """Result of supersession check."""
    is_supersession: bool
    temporal_order: str = ""  # "b_after_a", "a_after_b"
    supersession_date: date | None = None
    confidence: float = 0.0
    explanation: str = ""


class TemporalReasoner:
    """
    Handles temporal reasoning for fact comparison.

    Distinguishes document_date from fact validity dates.
    Detects SUPERSEDES vs CONTRADICTS based on temporal ordering.
    """

    # Keywords indicating state changes (supersession signals)
    STATE_CHANGE_KEYWORDS = [
        "resigned", "retired", "stepped down", "appointed", "named",
        "replaced", "succeeded", "effective", "former", "new",
        "transitioned", "ceased", "terminated", "expired",
        "was previously", "previously held", "took over",
    ]

    def check_supersession(self, fact_a, fact_b) -> SupersessionResult | None:
        """
        Check if one fact supersedes the other based on temporal ordering.
        Returns SupersessionResult if supersession is detected, None otherwise.
        """
        # Determine temporal ordering
        date_a = self._get_effective_date(fact_a)
        date_b = self._get_effective_date(fact_b)

        if not date_a or not date_b:
            return None

        if date_a == date_b:
            return None

        # Check for state change language
        has_change_a = self._has_state_change_language(fact_a.original_text)
        has_change_b = self._has_state_change_language(fact_b.original_text)

        # If the later fact has state-change language → SUPERSEDES
        if date_b > date_a and has_change_b:
            return SupersessionResult(
                is_supersession=True,
                temporal_order="b_after_a",
                supersession_date=date_b,
                confidence=0.85,
                explanation=(
                    f"Fact B (dated {date_b}) appears to supersede Fact A (dated {date_a}). "
                    f"Fact B contains state-change language indicating an update."
                ),
            )
        elif date_a > date_b and has_change_a:
            return SupersessionResult(
                is_supersession=True,
                temporal_order="a_after_b",
                supersession_date=date_a,
                confidence=0.85,
                explanation=(
                    f"Fact A (dated {date_a}) appears to supersede Fact B (dated {date_b}). "
                    f"Fact A contains state-change language indicating an update."
                ),
            )

        # If values differ and there's clear temporal ordering, it might still be supersession
        # even without explicit state-change language (e.g., new CEO without "appointed")
        if date_b > date_a:
            # Later document might simply report the current state
            return SupersessionResult(
                is_supersession=True,
                temporal_order="b_after_a",
                supersession_date=date_b,
                confidence=0.6,
                explanation=(
                    f"Fact B (dated {date_b}) is from a later document than Fact A (dated {date_a}). "
                    f"The newer document may reflect an updated state."
                ),
            )
        elif date_a > date_b:
            return SupersessionResult(
                is_supersession=True,
                temporal_order="a_after_b",
                supersession_date=date_a,
                confidence=0.6,
                explanation=(
                    f"Fact A (dated {date_a}) is from a later document than Fact B (dated {date_b}). "
                    f"The newer document may reflect an updated state."
                ),
            )

        return None

    def periods_overlap(self, fact_a, fact_b) -> bool:
        """Check if two facts' reporting periods overlap."""
        start_a = fact_a.fact_time_start
        end_a = fact_a.fact_time_end
        start_b = fact_b.fact_time_start
        end_b = fact_b.fact_time_end

        if not (start_a and end_a and start_b and end_b):
            # If we don't have explicit period dates, compare fiscal year/quarter
            if fact_a.fiscal_year and fact_b.fiscal_year:
                if fact_a.fiscal_year != fact_b.fiscal_year:
                    return False
                if fact_a.fiscal_quarter and fact_b.fiscal_quarter:
                    return fact_a.fiscal_quarter == fact_b.fiscal_quarter
            return True  # Assume overlap if we can't determine

        # Check date range overlap
        return start_a <= end_b and start_b <= end_a

    def _get_effective_date(self, fact) -> date | None:
        """Get the most relevant date for temporal ordering."""
        for attr in ["document_date", "fact_date_exact", "valid_from", "validity_start", "fact_time_start"]:
            val = getattr(fact, attr, None)
            if val:
                if isinstance(val, str):
                    try:
                        from datetime import datetime
                        return datetime.fromisoformat(val[:10]).date()
                    except Exception:
                        pass
                elif isinstance(val, date):
                    return val
        return None

    def _has_state_change_language(self, text: str | None) -> bool:
        """Check if text contains state-change keywords."""
        if not text:
            return False
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.STATE_CHANGE_KEYWORDS)
