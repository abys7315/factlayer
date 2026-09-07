"""Document-level context extraction — organization, type, period, currency, etc."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.config import get_settings


@dataclass
class DocumentContext:
    """Extracted document-level context."""
    organization: str | None = None
    document_type: str | None = None
    document_title: str | None = None
    publication_date: date | None = None
    reporting_period_start: date | None = None
    reporting_period_end: date | None = None
    default_currency: str | None = None
    geography: str | None = None
    language: str = "en"
    fiscal_year_end_month: int | None = None


class DocumentContextResolver:
    """
    Extracts document-level context using heuristics on first pages + metadata,
    with optional LLM call for gap-filling.

    Facts inherit relevant context from this when their own blocks lack it.
    Never infers unsupported context.
    """

    # Common document type patterns
    DOC_TYPE_PATTERNS = {
        "annual_report": [r"annual\s+report", r"yearly\s+report"],
        "quarterly_report": [r"quarterly\s+(report|results|filing)", r"q[1-4]\s+\d{4}"],
        "investor_presentation": [r"investor\s+(presentation|day|update)", r"earnings\s+(call|presentation)"],
        "press_release": [r"press\s+release", r"news\s+release", r"media\s+release"],
        "prospectus": [r"prospectus", r"offering\s+memorandum"],
        "filing": [r"10-k", r"10-q", r"20-f", r"8-k", r"form\s+\d"],
    }

    CURRENCY_PATTERNS = {
        "USD": [r"\$", r"USD", r"US\s+[Dd]ollars?", r"United\s+States\s+[Dd]ollars?"],
        "EUR": [r"€", r"EUR", r"[Ee]uros?"],
        "GBP": [r"£", r"GBP", r"[Pp]ounds?\s+[Ss]terling"],
        "INR": [r"₹", r"INR", r"[Ii]ndian\s+[Rr]upees?"],
        "JPY": [r"¥", r"JPY", r"[Jj]apanese\s+[Yy]en"],
    }

    FISCAL_YEAR_PATTERN = re.compile(
        r"(?:FY|fiscal\s+year)\s*(\d{4}(?:\s*[-–]\s*\d{2,4})?)", re.IGNORECASE
    )
    DATE_PATTERNS = [
        re.compile(r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})", re.IGNORECASE),
        re.compile(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})", re.IGNORECASE),
        re.compile(r"(\d{4})-(\d{2})-(\d{2})"),
    ]

    MONTH_MAP = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }

    def extract_context(self, pages_text: list[str], metadata: dict[str, Any]) -> DocumentContext:
        """Extract document context from first few pages and metadata."""
        ctx = DocumentContext()

        # Combine first 3-5 pages for analysis
        analysis_text = "\n".join(pages_text[:5])
        first_page = pages_text[0] if pages_text else ""

        # 1. Document title from metadata or first page
        ctx.document_title = self._extract_title(metadata, first_page)

        # 2. Organization name
        ctx.organization = self._extract_organization(first_page, analysis_text)

        # 3. Document type
        ctx.document_type = self._detect_document_type(analysis_text)

        # 4. Publication date
        ctx.publication_date = self._extract_publication_date(metadata, first_page)

        # 5. Currency
        ctx.default_currency = self._detect_currency(analysis_text)

        # 6. Reporting period
        self._extract_reporting_period(ctx, analysis_text)

        # 7. Geography
        ctx.geography = self._detect_geography(analysis_text)

        return ctx

    def _extract_title(self, metadata: dict, first_page: str) -> str | None:
        """Extract document title from PDF metadata or first page."""
        # Try metadata first
        title = metadata.get("title", "")
        if title and len(title) > 3 and title.lower() not in ("untitled", "microsoft word"):
            return title.strip()

        # Extract from first page: likely the largest/first substantial line
        lines = [l.strip() for l in first_page.split("\n") if l.strip() and len(l.strip()) > 3]
        for line in lines[:5]:
            # Skip very short lines and lines that look like dates or numbers
            if len(line) > 5 and not line.isdigit() and not re.match(r"^\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}$", line):
                return line
        return None

    def _extract_organization(self, first_page: str, full_text: str) -> str | None:
        """Extract organization name from first page."""
        lines = [l.strip() for l in first_page.split("\n") if l.strip()]

        # Common patterns: "Acme Corporation", "Acme Inc.", "Acme Ltd."
        org_suffixes = r"(?:Inc\.?|Corp\.?|Corporation|Ltd\.?|Limited|LLC|LLP|PLC|plc|Group|Holdings|Co\.?)"
        org_pattern = re.compile(rf"(\b[A-Z][\w\s&]+{org_suffixes})\b")

        for line in lines[:10]:
            match = org_pattern.search(line)
            if match:
                return match.group(1).strip()

        return None

    def _detect_document_type(self, text: str) -> str | None:
        """Detect document type from text patterns."""
        text_lower = text.lower()
        for doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return doc_type
        return None

    def _extract_publication_date(self, metadata: dict, first_page: str) -> date | None:
        """Extract publication/creation date."""
        # Try metadata
        for key in ("creationDate", "modDate"):
            val = metadata.get(key, "")
            if val:
                parsed = self._parse_pdf_date(val)
                if parsed:
                    return parsed

        # Try first page text
        for pattern in self.DATE_PATTERNS:
            match = pattern.search(first_page)
            if match:
                parsed = self._parse_date_match(match)
                if parsed:
                    return parsed

        return None

    def _parse_pdf_date(self, date_str: str) -> date | None:
        """Parse PDF metadata date format: D:YYYYMMDDHHmmSS."""
        try:
            cleaned = date_str.replace("D:", "").strip()
            if len(cleaned) >= 8:
                return date(int(cleaned[:4]), int(cleaned[4:6]), int(cleaned[6:8]))
        except (ValueError, IndexError):
            pass
        return None

    def _parse_date_match(self, match: re.Match) -> date | None:
        """Parse a date from regex match groups."""
        try:
            groups = match.groups()
            if len(groups) == 3:
                # Try different formats
                for g in groups:
                    if g.lower() in self.MONTH_MAP:
                        month = self.MONTH_MAP[g.lower()]
                        nums = [int(x) for x in groups if x.isdigit()]
                        if len(nums) == 2:
                            year = max(nums)
                            day = min(nums) if min(nums) <= 31 else 1
                            return date(year, month, day)
                # ISO format
                if all(g.isdigit() for g in groups):
                    return date(int(groups[0]), int(groups[1]), int(groups[2]))
        except (ValueError, IndexError):
            pass
        return None

    def _detect_currency(self, text: str) -> str | None:
        """Detect default currency from text patterns."""
        # Count occurrences of each currency indicator
        scores: dict[str, int] = {}
        for currency, patterns in self.CURRENCY_PATTERNS.items():
            count = sum(len(re.findall(p, text[:5000])) for p in patterns)
            if count > 0:
                scores[currency] = count

        if scores:
            return max(scores, key=scores.get)
        return None

    def _extract_reporting_period(self, ctx: DocumentContext, text: str) -> None:
        """Extract fiscal year / reporting period."""
        match = self.FISCAL_YEAR_PATTERN.search(text)
        if match:
            fy_str = match.group(1).strip()
            # Parse "2025" or "2024-25" or "2024-2025"
            parts = re.split(r'[-–]', fy_str)
            try:
                start_year = int(parts[0])
                if len(parts) > 1:
                    end_str = parts[1].strip()
                    end_year = int(end_str) if len(end_str) == 4 else int(f"{str(start_year)[:2]}{end_str}")
                else:
                    end_year = start_year

                # Default: April-March for Indian FY, Jan-Dec otherwise
                ctx.reporting_period_start = date(start_year, 1, 1)
                ctx.reporting_period_end = date(end_year, 12, 31)
            except (ValueError, IndexError):
                pass

    def _detect_geography(self, text: str) -> str | None:
        """Detect geographic scope."""
        text_lower = text[:3000].lower()
        geo_keywords = {
            "global": ["global", "worldwide", "international"],
            "United States": ["united states", "u.s.", "usa", "american"],
            "India": ["india", "indian"],
            "United Kingdom": ["united kingdom", "u.k.", "british"],
            "European Union": ["european union", "eu"],
        }
        for geo, keywords in geo_keywords.items():
            if any(kw in text_lower for kw in keywords):
                return geo
        return None
