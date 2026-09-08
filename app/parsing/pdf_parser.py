"""PDF parsing, layout analysis, block and table extraction using PyMuPDF (fitz)."""

from __future__ import annotations

import io
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

import fitz  # pymupdf

from app.models.enums import BlockType


@dataclass
class ParsedBlock:
    """A content block extracted from a PDF page."""
    block_type: str
    content: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1
    sequence_number: int
    structured_content: dict | None = None


@dataclass
class ParsedTable:
    """Structured table data preserving headers, rows, and coordinates."""
    headers: list[list[str]]
    rows: list[dict[str, Any]]
    bbox: tuple[float, float, float, float]
    footnotes: list[str] = field(default_factory=list)
    units_detected: str | None = None
    raw_cells: list[list[str | None]] = field(default_factory=list)
    markdown: str = ""
    is_garbled: bool = False


@dataclass
class ParsedFigure:
    """An image/figure extracted from a PDF page."""
    bbox: tuple[float, float, float, float]
    image_data: bytes | None = None
    image_ext: str = "png"
    caption: str | None = None
    width: int = 0
    height: int = 0


@dataclass
class ParsedPage:
    """All extracted content from a single PDF page."""
    page_number: int
    width: float
    height: float
    raw_text: str
    blocks: list[ParsedBlock]
    tables: list[ParsedTable]
    figures: list[ParsedFigure]
    text_quality_score: float = 1.0  # 0-1, low = needs OCR


@dataclass
class ParsedDocument:
    """Complete parsed PDF document."""
    page_count: int
    pages: list[ParsedPage]
    metadata: dict[str, Any]


class PDFParser:
    """
    Primary PDF parser using PyMuPDF (fitz).
    Extracts per-page: raw text, typed content blocks with bbox,
    tables with full structure, and figures/images.
    """

    MIN_TEXT_LENGTH = 30
    MIN_TEXT_QUALITY = 0.3

    def parse(self, file_data: bytes) -> ParsedDocument:
        """Parse a PDF file and return structured content using high-speed PyMuPDF engine."""
        pages: list[ParsedPage] = []
        doc = fitz.open(stream=file_data, filetype="pdf")
        metadata = dict(doc.metadata) if doc.metadata else {}
        page_count = len(doc)

        for page_num in range(page_count):
            fitz_page = doc[page_num]
            parsed_page = self._parse_page(fitz_page, page_num + 1)
            pages.append(parsed_page)

        doc.close()
        return ParsedDocument(page_count=page_count, pages=pages, metadata=metadata)

    def _parse_page(self, fitz_page, page_number: int) -> ParsedPage:
        """Parse a single page using fast PyMuPDF."""
        rect = fitz_page.rect
        width = float(rect.width) if rect.width > 0 else 612.0
        height = float(rect.height) if rect.height > 0 else 792.0

        raw_text = fitz_page.get_text() or ""
        text_quality = self._assess_text_quality(raw_text, width, height)

        # Extract tables via PyMuPDF with sanity checking and vision fallback
        # Discard misdetected charts (< 2 real data rows or chart dimensions) so they fall through to text blocks
        tables = self._extract_tables(fitz_page, page_number)
        valid_tables = [t for t in tables if not t.is_garbled]
        table_bboxes = [t.bbox for t in valid_tables]

        # Extract text blocks (only valid tabular grids suppress text overlap)
        blocks = self._extract_blocks(fitz_page, raw_text, table_bboxes)

        # Add valid table blocks
        for i, table in enumerate(valid_tables):
            table_block = ParsedBlock(
                block_type=BlockType.TABLE.value,
                content=table.markdown or self._table_to_text(table),
                bbox=table.bbox,
                sequence_number=len(blocks) + i,
                structured_content={
                    "headers": table.headers,
                    "rows": table.rows,
                    "footnotes": table.footnotes,
                    "units_detected": table.units_detected,
                    "raw_cells": table.raw_cells,
                    "markdown": table.markdown,
                    "is_garbled": False,
                },
            )
            blocks.append(table_block)

        # Sort blocks by vertical position (top to bottom)
        blocks.sort(key=lambda b: (b.bbox[1], b.bbox[0]))
        for i, block in enumerate(blocks):
            block.sequence_number = i

        # Extract figures/images
        figures = self._extract_figures(fitz_page)

        return ParsedPage(
            page_number=page_number,
            width=width,
            height=height,
            raw_text=raw_text,
            blocks=blocks,
            tables=valid_tables,
            figures=figures,
            text_quality_score=text_quality,
        )

    def _assess_text_quality(self, text: str, page_width: float, page_height: float) -> float:
        """Assess text extraction quality."""
        if not text or len(text.strip()) < self.MIN_TEXT_LENGTH:
            return 0.0
        printable_ratio = sum(1 for c in text if c.isprintable() or c.isspace()) / len(text)
        if printable_ratio < 0.8:
            return 0.2
        words = text.split()
        if len(words) < 5:
            return 0.3
        return min(1.0, printable_ratio)

    def _extract_tables(self, fitz_page, page_number: int = 1, plumber_page: Any = None) -> list[ParsedTable]:
        """Extract tables using PyMuPDF find_tables() and pdfplumber with sanity check and Gemini Vision fallback."""
        tables: list[ParsedTable] = []
        try:
            tab_finder = fitz_page.find_tables()
            if tab_finder and tab_finder.tables:
                for tab in tab_finder.tables:
                    extracted = tab.extract()
                    if not extracted or len(extracted) < 1:
                        continue
                    bbox = (float(tab.bbox[0]), float(tab.bbox[1]), float(tab.bbox[2]), float(tab.bbox[3]))
                    parsed = self._structure_table(extracted, bbox)
                    if parsed:
                        tables.append(parsed)
        except Exception:
            pass

        # Fallback to pdfplumber if PyMuPDF detected 0 tables
        if not tables and plumber_page is not None:
            try:
                plumber_tables = plumber_page.extract_tables()
                for ptab in plumber_tables:
                    if ptab and len(ptab) >= 2:
                        parsed = self._structure_table(ptab, (0, 0, fitz_page.rect.width, fitz_page.rect.height))
                        if parsed:
                            tables.append(parsed)
            except Exception:
                pass

        # If any table is garbled, attempt vision fallback
        if any(t.is_garbled for t in tables):
            try:
                from backend.table_parser import TableParser
                table_parser = TableParser()
                vision_tables = table_parser._extract_tables_with_gemini_vision(fitz_page, page_number)
                if vision_tables:
                    clean_tables = []
                    for vt in vision_tables:
                        parsed = self._structure_table(vt.raw_cells, vt.bbox or (0, 0, fitz_page.rect.width, fitz_page.rect.height))
                        if parsed and not parsed.is_garbled:
                            clean_tables.append(parsed)
                    if clean_tables:
                        return clean_tables
            except Exception:
                pass

        # Return only healthy, non-garbled tables
        return [t for t in tables if not t.is_garbled]

    def _is_table_healthy(
        self,
        cleaned_matrix: list[list[str]],
        bbox: tuple[float, float, float, float] | None = None,
    ) -> tuple[bool, str]:
        """
        Sanity check table integrity to flag broken/garbled tables and misdetected charts:
        - At least 1 header row + at least 2 real data rows (len >= 3)
        - At least 2 columns (max_cols >= 2)
        - Not matching chart-like aspect ratio (tall height with sparse rows)
        - Body data cells are mostly numeric / short text (not paragraphs)
        - Empty cell ratio <= 50%, empty header ratio <= 60%
        """
        if len(cleaned_matrix) < 3:
            return False, "Fewer than 2 real data rows (requires header + >= 2 data rows)"

        col_counts = [len(r) for r in cleaned_matrix]
        max_cols = max(col_counts)
        min_cols = min(col_counts)

        if max_cols < 2:
            return False, "Single column detected (likely paragraph text)"

        # Check header non-empty ratio
        headers = cleaned_matrix[0]
        empty_headers = sum(1 for h in headers if not h.strip())
        if len(headers) > 0 and (empty_headers / len(headers)) > 0.60:
            return False, "More than 60% empty headers"

        # Check total cells empty ratio (50% threshold)
        total_cells = sum(len(r) for r in cleaned_matrix)
        empty_cells = sum(1 for r in cleaned_matrix for c in r if not c.strip())
        if total_cells > 0 and (empty_cells / total_cells) > 0.50:
            return False, "High empty cell ratio (> 50%)"

        # Check average and max cell text length
        total_len = sum(len(c) for r in cleaned_matrix for c in r)
        max_cell_len = max((len(c) for r in cleaned_matrix for c in r), default=0)
        avg_cell_len = total_len / max(1, total_cells)
        if max_cell_len > 250 or avg_cell_len > 120:
            return False, "Mashed text block detected in cells (max > 250 or avg > 120 chars)"

        # Check chart aspect ratio & row height anomalies
        if bbox and len(bbox) == 4:
            tbl_height = max(1.0, float(bbox[3]) - float(bbox[1]))
            num_rows = len(cleaned_matrix)
            avg_row_height = tbl_height / max(1, num_rows)

            # In PDFs, standard table rows are 10-35 points tall.
            # If the detected box is tall (> 100pt) with few rows (avg row height > 40pt or height > 120pt for <= 3 rows),
            # it is a graphical chart/plot area rather than a dense tabular grid.
            if (tbl_height > 100.0 and avg_row_height > 40.0) or (tbl_height > 120.0 and num_rows <= 3):
                return False, f"Chart-like dimensions detected (height={tbl_height:.1f}pt, avg_row_height={avg_row_height:.1f}pt for {num_rows} rows)"

        # Verify body data cells: financial tables contain numeric/metric or short-text values
        data_rows = cleaned_matrix[1:]
        data_cells = [c.strip() for r in data_rows for c in r if c.strip()]
        if not data_cells:
            return False, "No data cells in body rows"

        numeric_or_short_cells = 0
        for cell in data_cells:
            # Check for numbers, currency symbols, percentages, or concise labels <= 35 chars
            if re.search(r'[\$€£₹¥\d%]', cell) or len(cell) <= 35:
                numeric_or_short_cells += 1

        if (numeric_or_short_cells / len(data_cells)) < 0.50:
            return False, "Less than 50% numeric or short-text data cells (likely mashed paragraph text)"

        return True, "Healthy"

    def _structure_table(self, raw_cells: list[list[str | None]], bbox: tuple[float, float, float, float]) -> ParsedTable | None:
        """Process raw cell matrix into structured ParsedTable."""
        cleaned_matrix = []
        for row in raw_cells:
            cleaned_row = [str(c).strip() if c is not None else "" for c in row]
            if any(cleaned_row):
                cleaned_matrix.append(cleaned_row)

        if len(cleaned_matrix) < 2:
            return None

        is_healthy, health_reason = self._is_table_healthy(cleaned_matrix, bbox)

        header_row = cleaned_matrix[0]
        headers = [header_row]

        rows = []
        for row in cleaned_matrix[1:]:
            row_dict = {}
            for col_idx, cell_value in enumerate(row):
                col_name = header_row[col_idx] if col_idx < len(header_row) and header_row[col_idx] else f"Column_{col_idx + 1}"
                row_dict[col_name] = cell_value
            rows.append(row_dict)

        # Detect units
        units_detected = None
        for text in header_row:
            if "$" in text or "usd" in text.lower():
                units_detected = "USD"
            elif "₹" in text or "inr" in text.lower() or "rs" in text.lower() or "rupees" in text.lower():
                units_detected = "INR"
            elif "%" in text or "percent" in text.lower():
                units_detected = "%"

        # Construct clean Markdown table representation
        md_lines = []
        md_lines.append("| " + " | ".join(header_row) + " |")
        md_lines.append("| " + " | ".join(["---"] * len(header_row)) + " |")
        for row in cleaned_matrix[1:]:
            # Pad row if needed
            padded = row + [""] * (len(header_row) - len(row))
            md_lines.append("| " + " | ".join(padded[:len(header_row)]) + " |")
        markdown_table = "\n".join(md_lines)

        return ParsedTable(
            headers=headers,
            rows=rows,
            bbox=bbox,
            footnotes=[],
            units_detected=units_detected,
            raw_cells=cleaned_matrix,
            markdown=markdown_table,
            is_garbled=not is_healthy,
        )

    def _table_to_text(self, table: ParsedTable) -> str:
        """Convert a ParsedTable to markdown/text representation."""
        if table.markdown:
            return table.markdown
        lines = []
        if table.headers:
            for hrow in table.headers:
                lines.append(" | ".join(hrow))
            lines.append(" | ".join(["---"] * len(table.headers[0])))
        for r in table.rows:
            lines.append(" | ".join(str(v) for v in r.values()))
        return "\n".join(lines)

    # ── Line merging constants ──
    # Maximum horizontal gap (points) between two blocks to consider them in the same column
    COLUMN_X_TOLERANCE = 10.0
    # Maximum vertical gap (points) between consecutive lines to merge them
    LINE_GAP_TOLERANCE = 25.0
    # Minimum right-edge alignment tolerance for same-column detection
    COLUMN_RIGHT_TOLERANCE = 30.0

    def _extract_blocks(self, fitz_page, raw_text: str, table_bboxes: list[tuple[float, float, float, float]]) -> list[ParsedBlock]:
        """
        Extract text blocks using PyMuPDF, then merge scattered single-line
        blocks into coherent paragraph blocks based on column alignment and
        vertical proximity.

        Many PDFs (especially government reports) produce one raw block per
        typographic line.  Without merging, each 40-char fragment gets
        classified and sent to the LLM independently, which destroys
        extraction quality.
        """
        # Step 1: Collect raw line-level blocks, filtering table overlaps
        raw_lines: list[dict] = []
        raw_blocks = fitz_page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)

        for rb in raw_blocks:
            if len(rb) < 5:
                continue
            # block_type == 1 means image block in PyMuPDF
            if len(rb) >= 7 and rb[6] == 1:
                continue
            x0, y0, x1, y1 = float(rb[0]), float(rb[1]), float(rb[2]), float(rb[3])
            text = rb[4] if isinstance(rb[4], str) else ""
            text = text.strip()
            if not text:
                continue
            bbox = (x0, y0, x1, y1)
            # Skip blocks that overlap with detected tables
            overlaps_table = any(
                self._bbox_overlap(bbox, t_bbox) > 0.5
                for t_bbox in table_bboxes
            )
            if overlaps_table:
                continue
            raw_lines.append({"text": text, "bbox": bbox})

        # Step 2: Merge consecutive lines from the same column into paragraphs
        merged_groups = self._merge_lines_into_paragraphs(raw_lines, fitz_page.rect.height)

        # Step 3: Build ParsedBlocks from merged groups
        blocks: list[ParsedBlock] = []
        for seq, group in enumerate(merged_groups):
            btype = self._classify_block_text(group["text"], group["bbox"], fitz_page.rect.height)
            blocks.append(
                ParsedBlock(
                    block_type=btype,
                    content=group["text"],
                    bbox=group["bbox"],
                    sequence_number=seq,
                )
            )
        return blocks

    def _merge_lines_into_paragraphs(
        self,
        raw_lines: list[dict],
        page_height: float,
    ) -> list[dict]:
        """
        Merge consecutive single-line blocks that share column alignment
        and have small vertical gaps into coherent paragraph blocks.

        Handles two-column layouts by detecting left-edge alignment:
        lines whose x0 values are within COLUMN_X_TOLERANCE of each other
        are considered part of the same column.
        """
        if not raw_lines:
            return []

        # Sort by vertical position (top to bottom), then left to right
        sorted_lines = sorted(raw_lines, key=lambda r: (r["bbox"][1], r["bbox"][0]))

        # Group lines into columns first, then merge within each column
        # Detect column x-positions by clustering left edges
        x_positions = sorted(set(round(r["bbox"][0], 0) for r in sorted_lines))
        columns: list[float] = []
        for x in x_positions:
            if not columns or abs(x - columns[-1]) > self.COLUMN_X_TOLERANCE:
                columns.append(x)

        # Assign each line to a column
        column_lines: dict[int, list[dict]] = {i: [] for i in range(len(columns))}
        for line in sorted_lines:
            x0 = line["bbox"][0]
            best_col = 0
            best_dist = abs(x0 - columns[0])
            for ci, cx in enumerate(columns):
                dist = abs(x0 - cx)
                if dist < best_dist:
                    best_dist = dist
                    best_col = ci
            column_lines[best_col].append(line)

        # Merge within each column: consecutive lines with small vertical gaps
        merged: list[dict] = []
        for col_idx in sorted(column_lines.keys()):
            lines = column_lines[col_idx]
            if not lines:
                continue
            # Sort column lines by y-position
            lines.sort(key=lambda r: r["bbox"][1])

            current_group = {
                "texts": [lines[0]["text"]],
                "x0": lines[0]["bbox"][0],
                "y0": lines[0]["bbox"][1],
                "x1": lines[0]["bbox"][2],
                "y1": lines[0]["bbox"][3],
            }

            for i in range(1, len(lines)):
                prev_bottom = current_group["y1"]
                cur_top = lines[i]["bbox"][1]
                cur_x0 = lines[i]["bbox"][0]
                vertical_gap = cur_top - prev_bottom

                # Check if this line belongs to the same paragraph:
                # - Small vertical gap (consecutive line)
                # - Similar left-edge alignment (same column/indent)
                left_aligned = abs(cur_x0 - current_group["x0"]) < self.COLUMN_X_TOLERANCE
                # Allow slightly indented continuation (e.g. paragraph number like "II.5.18\t")
                indent_continuation = (cur_x0 > current_group["x0"]) and (cur_x0 - current_group["x0"]) < 50

                same_paragraph = (
                    vertical_gap <= self.LINE_GAP_TOLERANCE
                    and vertical_gap >= -2  # Lines don't go backwards
                    and (left_aligned or indent_continuation)
                )

                # If this line starts with a new paragraph number (e.g. "II.5.20"),
                # start a new group even if it's close to the previous line
                new_para_marker = re.match(
                    r'^(?:II?\.\d+\.\d+|[IVX]+\.\d+\.\d+|\d+\.\d+\.\d+)\s',
                    lines[i]["text"]
                )

                if same_paragraph and not new_para_marker:
                    current_group["texts"].append(lines[i]["text"])
                    current_group["x0"] = min(current_group["x0"], cur_x0)
                    current_group["x1"] = max(current_group["x1"], lines[i]["bbox"][2])
                    current_group["y1"] = lines[i]["bbox"][3]
                else:
                    # Finalize current group
                    merged.append({
                        "text": " ".join(current_group["texts"]),
                        "bbox": (
                            current_group["x0"],
                            current_group["y0"],
                            current_group["x1"],
                            current_group["y1"],
                        ),
                    })
                    current_group = {
                        "texts": [lines[i]["text"]],
                        "x0": lines[i]["bbox"][0],
                        "y0": lines[i]["bbox"][1],
                        "x1": lines[i]["bbox"][2],
                        "y1": lines[i]["bbox"][3],
                    }

            # Don't forget the last group
            merged.append({
                "text": " ".join(current_group["texts"]),
                "bbox": (
                    current_group["x0"],
                    current_group["y0"],
                    current_group["x1"],
                    current_group["y1"],
                ),
            })

        # Sort final merged blocks by reading order: column by column (left-to-right), top-to-bottom within each column
        is_multi_column = len(columns) > 1 and (max(columns) - min(columns)) > 120
        if is_multi_column:
            def reading_order_key(g):
                col_idx = min(range(len(columns)), key=lambda ci: abs(g["bbox"][0] - columns[ci]))
                return (col_idx, g["bbox"][1])
            merged.sort(key=reading_order_key)
        else:
            merged.sort(key=lambda g: (g["bbox"][1], g["bbox"][0]))
        return merged

    def _classify_block_text(self, text: str, bbox: tuple[float, float, float, float], page_height: float) -> str:
        """Classify block into heading, footnote, header, footer, or body text."""
        lines = text.strip().split("\n")
        first_line = lines[0].strip()

        # Header / Footer by vertical position
        if bbox[1] < 45:
            return BlockType.PAGE_HEADER.value
        if bbox[3] > page_height - 45:
            return BlockType.PAGE_FOOTER.value

        # Footnote
        if (re.match(r"^(\*|\d{1,2}\s|[a-z]\))\s+", first_line) and len(text) < 200) or "source:" in first_line.lower():
            return BlockType.FOOTNOTE.value

        # Heading: short text, all-caps or section label, NOT a merged paragraph
        # A merged paragraph will be > 120 chars so it falls through correctly
        word_count = len(text.split())
        if (
            len(text) < 120
            and word_count <= 15
            and (len(lines) <= 2)
            and (
                text.isupper()
                or re.match(r"^(Section|Chapter|Part|Annex|Appendix)\s+", first_line, re.IGNORECASE)
            )
        ):
            return BlockType.HEADING.value

        return BlockType.PARAGRAPH.value

    def _extract_figures(self, fitz_page) -> list[ParsedFigure]:
        """Extract figures and images from page."""
        figures: list[ParsedFigure] = []
        try:
            image_list = fitz_page.get_images(full=True)
            for img_info in image_list:
                xref = img_info[0]
                rects = fitz_page.get_image_rects(xref)
                for r in rects:
                    bbox = (float(r.x0), float(r.y0), float(r.x1), float(r.y1))
                    figures.append(
                        ParsedFigure(
                            bbox=bbox,
                            width=int(r.width),
                            height=int(r.height),
                        )
                    )
        except Exception:
            pass
        return figures

    def _bbox_overlap(self, b1: tuple[float, float, float, float], b2: tuple[float, float, float, float]) -> float:
        """Calculate intersection over area of b1."""
        dx = max(0.0, min(b1[2], b2[2]) - max(b1[0], b2[0]))
        dy = max(0.0, min(b1[3], b2[3]) - max(b1[1], b2[1]))
        intersection = dx * dy
        area1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
        if area1 <= 0:
            return 0.0
        return intersection / area1
