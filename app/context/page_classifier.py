"""Page classifier for adaptive extraction priority."""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.parsing.pdf_parser import ParsedPage
from app.models.enums import BlockType


@dataclass
class PageClassification:
    """Classification result for a single page."""
    page_type: str  # cover, toc, text, financial_table, chart, appendix, blank, legal
    fact_density: float  # 0.0-1.0
    table_density: float
    image_density: float
    text_density: float
    processing_priority: int  # 1 (highest) to 5 (lowest)


class PageClassifier:
    """
    Classifies pages by content type and estimates fact density.
    Used for adaptive extraction — high-value pages get processed first.
    """

    # Keywords indicating high-value content
    HIGH_VALUE_KEYWORDS = [
        r"\$", r"€", r"£", r"₹", r"\d+[,.]?\d*\s*(?:million|billion|mn|bn|crore|lakh)",
        r"revenue", r"profit", r"loss", r"income", r"ebitda", r"margin",
        r"growth", r"increased", r"decreased", r"declined",
        r"appointed", r"resigned", r"acquired", r"merged",
    ]

    TOC_PATTERNS = [
        r"table\s+of\s+contents", r"contents\s*$", r"index\s*$",
        r"\.\.\.\.\.", r"\.{5,}",  # Dot leaders
    ]

    LEGAL_PATTERNS = [
        r"disclaimer", r"forward[- ]looking\s+statements?",
        r"safe\s+harbor", r"risk\s+factors",
        r"this\s+(?:document|report|presentation)\s+(?:contains|includes)",
    ]

    def classify(self, page: ParsedPage) -> PageClassification:
        """Classify a single page."""
        text = page.raw_text or ""
        text_lower = text.lower()
        text_len = len(text.strip())

        # Count block types
        total_blocks = max(len(page.blocks), 1)
        table_blocks = sum(1 for b in page.blocks if b.block_type == BlockType.TABLE.value)
        text_blocks = sum(1 for b in page.blocks if b.block_type in (BlockType.TEXT.value, BlockType.HEADING.value))

        table_density = table_blocks / total_blocks
        image_density = len(page.figures) / max(total_blocks, 1)
        text_density = text_blocks / total_blocks

        # Detect page type
        page_type = self._detect_page_type(page, text_lower, text_len, table_density, image_density)

        # Estimate fact density
        fact_density = self._estimate_fact_density(text, text_lower, table_density)

        # Determine processing priority
        priority = self._compute_priority(page_type, fact_density, table_density)

        return PageClassification(
            page_type=page_type,
            fact_density=fact_density,
            table_density=table_density,
            image_density=image_density,
            text_density=text_density,
            processing_priority=priority,
        )

    def _detect_page_type(self, page: ParsedPage, text_lower: str, text_len: int, table_density: float, image_density: float) -> str:
        """Determine page type."""
        # Blank page
        if text_len < 20 and not page.figures:
            return "blank"

        # Cover page (page 1 with little text, often has images)
        if page.page_number == 1 and text_len < 500:
            return "cover"

        # Table of contents
        if any(re.search(p, text_lower) for p in self.TOC_PATTERNS):
            return "toc"

        # Financial table page
        if table_density > 0.3:
            return "financial_table"

        # Chart-heavy page
        if image_density > 0.5:
            return "chart"

        # Legal / disclaimer page
        if any(re.search(p, text_lower) for p in self.LEGAL_PATTERNS):
            return "legal"

        return "text"

    def _estimate_fact_density(self, text: str, text_lower: str, table_density: float) -> float:
        """Estimate how many extractable facts this page likely contains."""
        if not text.strip():
            return 0.0

        # Count high-value keyword matches
        keyword_matches = sum(
            len(re.findall(p, text_lower)) for p in self.HIGH_VALUE_KEYWORDS
        )

        # Normalize by text length
        density = min(1.0, keyword_matches / max(len(text.split()), 1) * 5)

        # Tables boost density
        density = min(1.0, density + table_density * 0.3)

        return round(density, 3)

    def _compute_priority(self, page_type: str, fact_density: float, table_density: float) -> int:
        """Compute processing priority (1=highest, 5=lowest)."""
        type_priorities = {
            "financial_table": 1,
            "text": 2,
            "chart": 2,
            "legal": 3,
            "toc": 4,
            "cover": 4,
            "blank": 5,
            "appendix": 3,
        }
        base = type_priorities.get(page_type, 3)

        # Boost priority for high fact density
        if fact_density > 0.5:
            base = max(1, base - 1)

        return base
