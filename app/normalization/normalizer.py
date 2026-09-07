"""Fact normalizer — values, dates, currencies, and context fingerprints."""

from __future__ import annotations

import re
from datetime import date
from typing import Any


class FactNormalizer:
    """
    Normalizes extracted fact values for consistent comparison.
    Also generates context fingerprints for fast grouping/dedup.
    """

    CURRENCY_SYMBOLS = {
        "$": "USD", "€": "EUR", "£": "GBP", "₹": "INR", "¥": "JPY",
    }

    MULTIPLIERS = {
        "thousand": 1e3, "thousands": 1e3, "k": 1e3,
        "million": 1e6, "millions": 1e6, "mn": 1e6, "mm": 1e6, "m": 1e6,
        "billion": 1e9, "billions": 1e9, "bn": 1e9, "b": 1e9,
        "trillion": 1e12, "trillions": 1e12, "tn": 1e12, "t": 1e12,
        "crore": 1e7, "crores": 1e7, "cr": 1e7,
        "lakh": 1e5, "lakhs": 1e5,
    }

    def normalize_numeric(self, value_str: str) -> tuple[float | None, str | None]:
        """
        Parse a numeric string into (float_value, unit).
        Returns (None, None) if not parseable.
        """
        if not value_str:
            return None, None

        text = value_str.strip()

        # Detect currency symbol
        currency = None
        for sym, code in self.CURRENCY_SYMBOLS.items():
            if sym in text:
                currency = code
                text = text.replace(sym, "").strip()
                break

        # Detect percentage
        if "%" in text or "percent" in text.lower():
            text = text.replace("%", "").replace("percent", "").strip()
            numeric = self._parse_number(text)
            return numeric, "%"

        # Detect multiplier
        multiplier = 1.0
        text_lower = text.lower()
        for word, mult in sorted(self.MULTIPLIERS.items(), key=lambda x: len(x[0]), reverse=True):
            if word in text_lower:
                multiplier = mult
                text = re.sub(re.escape(word), "", text, flags=re.IGNORECASE).strip()
                break

        # Parse the number
        numeric = self._parse_number(text)
        if numeric is not None:
            numeric *= multiplier

        return numeric, currency

    def _parse_number(self, text: str) -> float | None:
        """Parse a plain number string."""
        if not text:
            return None

        # Remove commas and spaces
        cleaned = text.replace(",", "").replace(" ", "").strip()

        # Handle parenthesized negatives
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]

        # Handle explicit negative
        cleaned = cleaned.replace("−", "-").replace("–", "-")

        try:
            return float(cleaned)
        except ValueError:
            return None

    def normalize_period(self, period_str: str | None) -> dict[str, Any]:
        """
        Normalize a reporting period string into structured components.
        Returns dict with fiscal_year, fiscal_quarter, start_date, end_date.
        """
        result: dict[str, Any] = {
            "fiscal_year": None,
            "fiscal_quarter": None,
            "start_date": None,
            "end_date": None,
            "label": period_str,
        }

        if not period_str:
            return result

        text = period_str.strip().upper()

        # Match FY patterns
        fy_match = re.search(r"FY\s*(\d{4}(?:\s*[-–]\s*\d{2,4})?)", text)
        if fy_match:
            result["fiscal_year"] = f"FY{fy_match.group(1).replace(' ', '')}"

        # Match quarter patterns
        q_match = re.search(r"Q([1-4])", text)
        if q_match:
            result["fiscal_quarter"] = f"Q{q_match.group(1)}"

        # Match half-year
        h_match = re.search(r"H([12])", text)
        if h_match:
            result["fiscal_quarter"] = f"H{h_match.group(1)}"

        # Match plain year
        if not result["fiscal_year"]:
            year_match = re.search(r"\b(20\d{2}|19\d{2})\b", text)
            if year_match:
                result["fiscal_year"] = f"FY{year_match.group(1)}"

        return result

    def normalize_name(self, name: str) -> str:
        """Normalize entity/predicate names for comparison."""
        # Strip common suffixes
        cleaned = name.strip()
        for suffix in [" Inc.", " Inc", " Corp.", " Corp", " Ltd.", " Ltd",
                       " Limited", " LLC", " LLP", " PLC", " plc", " Group",
                       " Holdings", " Co.", " Co"]:
            if cleaned.endswith(suffix):
                cleaned = cleaned[:-len(suffix)].strip()
                break

        return cleaned.strip()

    def normalize_value(self, raw_value: str, attribute: str = "") -> dict[str, Any] | str | float:
        """Helper to normalize raw extracted value into structured dict or primitive."""
        if not raw_value:
            return ""
        num, unit_or_curr = self.normalize_numeric(raw_value)
        if num is not None:
            if unit_or_curr == "%":
                return {"value": num, "unit": "%"}
            elif unit_or_curr:
                return {"value": int(num) if num.is_integer() else num, "currency": unit_or_curr}
            return int(num) if num.is_integer() else num
        return raw_value.strip()

    def normalize_date(self, date_str: str) -> str | None:
        """Parse natural language dates into YYYY-MM-DD."""
        if not date_str:
            return None
        # Common pattern: Month DD, YYYY
        months = {
            "january": "01", "february": "02", "march": "03", "april": "04",
            "may": "05", "june": "06", "july": "07", "august": "08",
            "september": "09", "october": "10", "november": "11", "december": "12"
        }
        for m_name, m_num in months.items():
            if m_name in date_str.lower():
                day_match = re.search(r"\b(\d{1,2})\b", date_str)
                year_match = re.search(r"\b(20\d{2}|19\d{2})\b", date_str)
                if day_match and year_match:
                    day = int(day_match.group(1))
                    year = year_match.group(1)
                    return f"{year}-{m_num}-{day:02d}"
        return date_str

    def normalize_temporal_scope(self, text: str, doc_date: str | None = None) -> dict[str, str]:
        """Convert fiscal period string to {start: YYYY-MM-DD, end: YYYY-MM-DD}."""
        year_match = re.search(r"\b(20\d{2})\b", text)
        if year_match:
            y = year_match.group(1)
            return {"start": f"{y}-01-01", "end": f"{y}-12-31"}
        if doc_date:
            return {"start": doc_date, "end": doc_date}
        return {"start": "2023-01-01", "end": "2023-12-31"}

    def build_context_fingerprint(
        self,
        entity: str,
        predicate: str,
        period: str | None = None,
        scope: str | None = None,
        geography: str | None = None,
        basis: str | None = None,
        unit: str | None = None,
    ) -> str:
        """
        Build canonical context fingerprint for fast grouping/dedup.
        Format: entity|predicate|period|scope|geography|basis|unit
        """
        parts = [
            self._fp_normalize(entity),
            self._fp_normalize(predicate),
            self._fp_normalize(period or ""),
            self._fp_normalize(scope or ""),
            self._fp_normalize(geography or ""),
            self._fp_normalize(basis or ""),
            self._fp_normalize(unit or ""),
        ]
        return "|".join(parts)

    def _fp_normalize(self, text: str) -> str:
        """Normalize a string for fingerprint use."""
        return re.sub(r'\s+', '_', text.strip().lower())


# Alias for backwards compatibility
DataNormalizer = FactNormalizer
