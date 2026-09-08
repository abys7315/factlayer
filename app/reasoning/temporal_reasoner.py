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
        "revised", "restated", "updated", "corrected", "amended", "reclassified",
    ]

    POINT_IN_TIME_PREDICATES = {
        "ceo", "chief executive officer", "cfo", "chief financial officer",
        "auditor", "headquarters", "status", "credit rating", "managing director",
        "board member", "director",
    }

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

        # Check for state change language in original text or source quote
        text_a = getattr(fact_a, "original_text", "") or ""
        text_b = getattr(fact_b, "original_text", "") or ""
        has_change_a = self._has_state_change_language(text_a)
        has_change_b = self._has_state_change_language(text_b)

        # If the later fact has explicit state-change language → SUPERSEDES
        if date_b > date_a and has_change_b:
            return SupersessionResult(
                is_supersession=True,
                temporal_order="b_after_a",
                supersession_date=date_b,
                confidence=0.85,
                explanation=(
                    f"Fact B (dated {date_b}) supersedes Fact A (dated {date_a}). "
                    f"Fact B contains state-change language indicating an update/restatement."
                ),
            )
        elif date_a > date_b and has_change_a:
            return SupersessionResult(
                is_supersession=True,
                temporal_order="a_after_b",
                supersession_date=date_a,
                confidence=0.85,
                explanation=(
                    f"Fact A (dated {date_a}) supersedes Fact B (dated {date_b}). "
                    f"Fact A contains state-change language indicating an update/restatement."
                ),
            )

        # If both facts refer to overlapping/same fiscal periods (e.g. FY23 vs FY23),
        # conflicting numeric or performance values are a CONTRADICTION, NOT a silent supersession.
        if self.periods_overlap(fact_a, fact_b):
            return None

        # Only point-in-time office/status facts with non-overlapping dates qualify as supersession without explicit keywords
        pred_a = getattr(fact_a, "predicate", "").lower().strip()
        pred_b = getattr(fact_b, "predicate", "").lower().strip()
        is_point_in_time = any(p in pred_a or p in pred_b for p in self.POINT_IN_TIME_PREDICATES)

        if is_point_in_time:
            if date_b > date_a:
                return SupersessionResult(
                    is_supersession=True,
                    temporal_order="b_after_a",
                    supersession_date=date_b,
                    confidence=0.75,
                    explanation=(
                        f"Fact B (dated {date_b}) is a later point-in-time status update than Fact A (dated {date_a})."
                    ),
                )
            elif date_a > date_b:
                return SupersessionResult(
                    is_supersession=True,
                    temporal_order="a_after_b",
                    supersession_date=date_a,
                    confidence=0.75,
                    explanation=(
                        f"Fact A (dated {date_a}) is a later point-in-time status update than Fact B (dated {date_b})."
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
        for attr in ["document_date", "fact_date_exact", "valid_from", "validity_start", "fact_time_start", "supersession_date"]:
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

        # Check fiscal year
        fy = getattr(fact, "fiscal_year", None)
        if fy:
            import re
            m = re.search(r"\b(20\d{2}|19\d{2})\b", str(fy))
            if m:
                y = int(m.group(1))
                return date(y, 12, 31)

        # Check time_period / text attributes
        import re
        for text_attr in ["time_period", "reporting_period_label", "original_text", "source_quote", "object_value"]:
            txt = getattr(fact, text_attr, None)
            if txt and isinstance(txt, str):
                m = re.search(r"\b(20\d{2}|19\d{2})\b", txt)
                if m:
                    y = int(m.group(1))
                    return date(y, 12, 31)
        return None

    def _has_state_change_language(self, text: str | None) -> bool:
        """Check if text contains state-change keywords."""
        if not text:
            return False
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.STATE_CHANGE_KEYWORDS)

