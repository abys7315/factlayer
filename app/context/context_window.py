"""Context window builder — assembles LLM input with surrounding context."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.context.document_context import DocumentContext
from app.context.section_context import SectionNode
from app.parsing.pdf_parser import ParsedBlock, ParsedPage
from app.models.enums import BlockType
from app.config import get_settings


@dataclass
class ContextWindow:
    """A context-enriched input window for LLM extraction."""
    document_context_header: str
    section_context: str
    page_context: str
    primary_evidence: str
    surrounding_context: str
    full_text: str = ""
    target_block: Any = None
    doc_context: Any = None

    def build(self) -> str:
        """Assemble the full context window text."""
        parts = []
        if self.document_context_header:
            parts.append(self.document_context_header)
        if self.section_context:
            parts.append(self.section_context)
        if self.page_context:
            parts.append(self.page_context)
        if self.surrounding_context:
            parts.append(f"CONTEXT:\n{self.surrounding_context}")
        parts.append(f"PRIMARY EVIDENCE:\n{self.primary_evidence}")
        self.full_text = "\n\n".join(parts)
        return self.full_text


class ContextWindowBuilder:
    """
    Builds context-aware input windows for LLM extraction.

    For each evidence candidate block, constructs a window containing:
    - Document context header
    - Section heading
    - Page number
    - Primary evidence
    - Surrounding blocks (headings, footnotes, captions, nearby paragraphs)
    - Table headers (if block is a table row)
    """

    # Max characters for surrounding context
    MAX_SURROUNDING_CHARS = 2000

    def __init__(self):
        self.settings = get_settings()

    def build_window(
        self,
        block: ParsedBlock,
        page: ParsedPage,
        doc_context: DocumentContext,
        section: SectionNode | None = None,
        all_page_blocks: list[ParsedBlock] | None = None,
    ) -> ContextWindow:
        """Build a context window for a candidate block."""

        # 1. Document context header
        doc_header = self._build_doc_header(doc_context)

        # 2. Section context
        section_text = ""
        if section:
            section_text = f"SECTION: {section.title}"
            if section.section_type:
                section_text += f" ({section.section_type})"

        # 3. Page context
        page_text = f"PAGE: {page.page_number}"

        # 4. Primary evidence
        primary = block.content

        # 5. Surrounding context
        surrounding = self._build_surrounding_context(
            block, page, all_page_blocks or page.blocks
        )

        window = ContextWindow(
            document_context_header=doc_header,
            section_context=section_text,
            page_context=page_text,
            primary_evidence=primary,
            surrounding_context=surrounding,
            target_block=block,
            doc_context=doc_context,
        )
        window.build()
        return window

    def build_table_window(
        self,
        table_block: ParsedBlock,
        page: ParsedPage,
        doc_context: DocumentContext,
        section: SectionNode | None = None,
    ) -> ContextWindow:
        """Build a context window specifically for table extraction."""
        doc_header = self._build_doc_header(doc_context)

        section_text = ""
        if section:
            section_text = f"SECTION: {section.title}"

        page_text = f"PAGE: {page.page_number}"

        # Build structured table representation
        structured = table_block.structured_content or {}
        table_text = self._format_table_for_llm(structured)

        # Find nearby footnotes and captions
        surrounding = self._find_nearby_footnotes(table_block, page.blocks)

        window = ContextWindow(
            document_context_header=doc_header,
            section_context=section_text,
            page_context=page_text,
            primary_evidence=table_text,
            surrounding_context=surrounding,
            target_block=table_block,
            doc_context=doc_context,
        )
        window.build()
        return window

    def _build_doc_header(self, ctx: DocumentContext) -> str:
        """Build document context header string."""
        parts = []
        if ctx.organization:
            parts.append(f"ORGANIZATION: {ctx.organization}")
        if ctx.document_title:
            parts.append(f"DOCUMENT: {ctx.document_title}")
        if ctx.document_type:
            parts.append(f"TYPE: {ctx.document_type}")
        if ctx.default_currency:
            parts.append(f"CURRENCY: {ctx.default_currency}")
        if ctx.geography:
            parts.append(f"GEOGRAPHY: {ctx.geography}")
        if ctx.reporting_period_start and ctx.reporting_period_end:
            parts.append(f"PERIOD: {ctx.reporting_period_start} to {ctx.reporting_period_end}")
        return " | ".join(parts) if parts else ""

    def _build_surrounding_context(
        self,
        target: ParsedBlock,
        page: ParsedPage,
        all_blocks: list[ParsedBlock],
    ) -> str:
        """Gather surrounding context: headings, footnotes, nearby text."""
        context_parts: list[str] = []
        chars_used = 0

        # Find the target's position
        target_seq = target.sequence_number
        target_y = target.bbox[1]

        for block in all_blocks:
            if block is target or block.sequence_number == target_seq:
                continue

            # Include preceding headings
            if block.block_type == BlockType.HEADING.value and block.sequence_number < target_seq:
                text = f"HEADING: {block.content}"
                if chars_used + len(text) < self.MAX_SURROUNDING_CHARS:
                    context_parts.append(text)
                    chars_used += len(text)

            # Include footnotes from same page
            elif block.block_type == BlockType.FOOTNOTE.value:
                text = f"FOOTNOTE: {block.content}"
                if chars_used + len(text) < self.MAX_SURROUNDING_CHARS:
                    context_parts.append(text)
                    chars_used += len(text)

            # Include captions near the target
            elif block.block_type == BlockType.CAPTION.value:
                dist = abs(block.bbox[1] - target_y)
                if dist < 100:
                    text = f"CAPTION: {block.content}"
                    if chars_used + len(text) < self.MAX_SURROUNDING_CHARS:
                        context_parts.append(text)
                        chars_used += len(text)

            # Include immediately adjacent text blocks
            elif block.block_type == BlockType.TEXT.value:
                seq_dist = abs(block.sequence_number - target_seq)
                if seq_dist <= 2:
                    text = block.content[:500]
                    if chars_used + len(text) < self.MAX_SURROUNDING_CHARS:
                        context_parts.append(text)
                        chars_used += len(text)

        return "\n".join(context_parts)

    def _format_table_for_llm(self, structured: dict) -> str:
        """Format structured table data for LLM consumption."""
        lines = []

        headers = structured.get("headers", [])
        if headers:
            lines.append("TABLE HEADERS:")
            for header_row in headers:
                lines.append(" | ".join(str(h) for h in header_row))
            lines.append("")

        rows = structured.get("rows", [])
        if rows:
            lines.append("TABLE DATA:")
            for row in rows:
                label = row.get("label", "")
                cells = row.get("cells", [])
                values = [c.get("value", "") for c in cells]
                lines.append(f"{label}: " + " | ".join(values) if label else " | ".join(values))

        footnotes = structured.get("footnotes", [])
        if footnotes:
            lines.append("")
            lines.append("TABLE FOOTNOTES:")
            for fn in footnotes:
                lines.append(f"  {fn}")

        units = structured.get("units_detected")
        if units:
            lines.append(f"\nUNITS: {units}")

        return "\n".join(lines)

    def _find_nearby_footnotes(self, table_block: ParsedBlock, all_blocks: list[ParsedBlock]) -> str:
        """Find footnotes near a table block."""
        footnotes = []
        table_bottom = table_block.bbox[3]

        for block in all_blocks:
            if block.block_type == BlockType.FOOTNOTE.value:
                # Footnotes below the table
                if block.bbox[1] >= table_bottom - 10:
                    footnotes.append(f"FOOTNOTE: {block.content}")

        return "\n".join(footnotes)
