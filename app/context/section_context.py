"""Section hierarchy builder from heading blocks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.parsing.pdf_parser import ParsedBlock, ParsedPage
from app.models.enums import BlockType


@dataclass
class SectionNode:
    """A node in the section hierarchy tree."""
    title: str
    level: int
    start_page: int
    end_page: int
    section_type: str | None = None
    children: list[SectionNode] = field(default_factory=list)
    block_indices: list[tuple[int, int]] = field(default_factory=list)  # (page_num, block_seq)


class SectionHierarchyBuilder:
    """
    Builds section/subsection hierarchy from heading blocks.

    Uses font size analysis, numbering patterns, and common section names.
    """

    SECTION_TYPE_KEYWORDS = {
        "financial": ["financial", "revenue", "income", "balance sheet", "cash flow", "profit", "loss", "earnings"],
        "governance": ["governance", "board", "director", "committee", "corporate governance"],
        "risk": ["risk", "risk management", "risk factors"],
        "legal": ["legal", "regulatory", "compliance", "litigation"],
        "operational": ["operations", "operational", "business overview", "strategy"],
        "hr": ["human resources", "employees", "workforce", "talent"],
        "esg": ["esg", "sustainability", "environmental", "social", "climate"],
    }

    def build_hierarchy(self, pages: list[ParsedPage]) -> list[SectionNode]:
        """Build section hierarchy from parsed pages."""
        headings: list[tuple[str, int, int]] = []  # (title, level, page_number)

        for page in pages:
            for block in page.blocks:
                if block.block_type == BlockType.HEADING.value:
                    level = self._estimate_heading_level(block)
                    headings.append((block.content, level, page.page_number))

        if not headings:
            return []

        return self._build_tree(headings, pages)

    def _estimate_heading_level(self, block: ParsedBlock) -> int:
        """Estimate heading level from content and formatting clues."""
        content = block.content.strip()

        # Check for numbered headings
        num_match = re.match(r'^(\d+(?:\.\d+)*)\s', content)
        if num_match:
            dots = num_match.group(1).count('.')
            return dots + 1

        # Use bbox height as proxy for font size (larger = higher level)
        block_height = abs(block.bbox[3] - block.bbox[1])
        if block_height > 20:
            return 1
        elif block_height > 15:
            return 2
        else:
            return 3

    def _classify_section_type(self, title: str) -> str | None:
        """Classify section type based on title keywords."""
        title_lower = title.lower()
        for section_type, keywords in self.SECTION_TYPE_KEYWORDS.items():
            if any(kw in title_lower for kw in keywords):
                return section_type
        return None

    def _build_tree(self, headings: list[tuple[str, int, int]], pages: list[ParsedPage]) -> list[SectionNode]:
        """Build a tree from flat heading list."""
        max_page = max(p.page_number for p in pages) if pages else 1
        sections: list[SectionNode] = []
        stack: list[SectionNode] = []

        for i, (title, level, page_num) in enumerate(headings):
            # End page = next heading's page - 1, or last page
            end_page = headings[i + 1][2] - 1 if i + 1 < len(headings) else max_page
            end_page = max(end_page, page_num)

            node = SectionNode(
                title=title,
                level=level,
                start_page=page_num,
                end_page=end_page,
                section_type=self._classify_section_type(title),
            )

            # Pop stack until we find a parent with a higher level
            while stack and stack[-1].level >= level:
                stack.pop()

            if stack:
                stack[-1].children.append(node)
            else:
                sections.append(node)

            stack.append(node)

        return sections
