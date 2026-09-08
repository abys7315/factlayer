"""Structural Table Parser with Sanity Checks and Gemini Vision Fallback.

1. Extracts tables structurally via PyMuPDF / pdfplumber on all pages (fast and free).
2. Runs sanity checks (row/col count, empty cell ratio, mashed text detection) to flag broken/garbled tables.
3. Falls back to Gemini Vision extraction specifically on flagged pages.
4. Produces clean, standardized Markdown tables and structured JSON suitable for fact extraction.
"""

from __future__ import annotations

import io
import os
import re
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from PIL import Image
import fitz  # PyMuPDF
from backend.table_cleaner import clean_table_headers, strip_table_artifacts

logger = logging.getLogger(__name__)

GEMINI_VISION_TABLE_PROMPT = """You are an expert document intelligence model specializing in table extraction.
Analyze this page image and extract all tables with high precision.

Return ONLY a JSON array of extracted tables. Each table object must have:
- "title": a descriptive title or header if visible, or null
- "headers": list of column header names
- "rows": list of rows, where each row is a list of cell string values corresponding to the headers
- "footnotes": list of footnote texts under the table, if any
- "markdown": a perfectly formatted GitHub Markdown representation of the table

Example JSON structure:
[
  {
    "title": "Consolidated Statements of Operations",
    "headers": ["Metric", "FY 2022", "FY 2023"],
    "rows": [
      ["Total Revenue", "$80,000,000", "$100,000,000"],
      ["Net Income", "$15,000,000", "$20,000,000"]
    ],
    "footnotes": ["All numbers in USD."],
    "markdown": "| Metric | FY 2022 | FY 2023 |\n| --- | --- | --- |\n| Total Revenue | $80,000,000 | $100,000,000 |\n| Net Income | $15,000,000 | $20,000,000 |"
  }
]

Do NOT output conversational text, explanations, or code blocks outside the JSON."""


@dataclass
class ExtractedTable:
    page_number: int
    headers: List[str]
    rows: List[List[str]]
    markdown: str
    is_garbled: bool = False
    extraction_source: str = "structural"  # "structural" or "gemini_vision"
    bbox: Optional[Tuple[float, float, float, float]] = None
    footnotes: List[str] = field(default_factory=list)
    raw_cells: List[List[str]] = field(default_factory=list)


class TableParser:
    """Multi-tier table parser: Fast structural extraction with sanity check & Gemini Vision fallback."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self._client = None
        self._legacy_model = None
        self._init_vision_client()

    def _init_vision_client(self):
        if not self.api_key:
            return
        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
            self._sdk_type = "google-genai"
            return
        except Exception:
            pass

        try:
            import google.generativeai as genai_legacy
            genai_legacy.configure(api_key=self.api_key)
            self._legacy_model = genai_legacy.GenerativeModel("gemini-flash-latest")
            self._sdk_type = "google.generativeai"
            return
        except Exception:
            pass

    def extract_tables_from_page(
        self,
        fitz_page: fitz.Page,
        page_number: int,
        pdfplumber_page: Any = None,
    ) -> List[ExtractedTable]:
        """
        Extract tables from a single page.
        1. Fast structural extraction via PyMuPDF / pdfplumber.
        2. Perform sanity checks.
        3. If broken/garbled or structural tables failed, invoke Gemini Vision fallback.
        """
        tables: List[ExtractedTable] = []

        # Tier 1: Try PyMuPDF native structural table finder
        try:
            tab_finder = fitz_page.find_tables()
            if tab_finder and tab_finder.tables:
                for tab in tab_finder.tables:
                    extracted = tab.extract()
                    if extracted and len(extracted) >= 2:
                        bbox = (float(tab.bbox[0]), float(tab.bbox[1]), float(tab.bbox[2]), float(tab.bbox[3]))
                        t = self._process_raw_matrix(extracted, page_number, bbox=bbox, source="pymupdf")
                        if t:
                            tables.append(t)
        except Exception as e:
            logger.debug(f"PyMuPDF find_tables failed on page {page_number}: {e}")

        # Tier 1b: If no tables from PyMuPDF, try pdfplumber if provided
        if not tables and pdfplumber_page is not None:
            try:
                extracted_plumber_tables = pdfplumber_page.extract_tables()
                for ptab in extracted_plumber_tables:
                    if ptab and len(ptab) >= 2:
                        t = self._process_raw_matrix(ptab, page_number, source="pdfplumber")
                        if t:
                            tables.append(t)
            except Exception as e:
                logger.debug(f"pdfplumber table extraction failed on page {page_number}: {e}")

        # Tier 2: Check for garbled tables or missing structural tables on dense table pages
        has_garbled = any(t.is_garbled for t in tables)
        page_text = fitz_page.get_text("text") or ""
        looks_like_tabular = self._heuristic_looks_like_table(page_text)

        # Fallback to Gemini Vision if tables are garbled OR if page has tabular structure but 0 structural tables found
        if (has_garbled or (looks_like_tabular and not tables)) and self._has_vision_capability():
            logger.info(f"Page {page_number}: Flagged for Gemini Vision table extraction (garbled={has_garbled}, tabular_heuristics={looks_like_tabular})")
            vision_tables = self._extract_tables_with_gemini_vision(fitz_page, page_number)
            if vision_tables:
                # Replace garbled or empty tables with clean vision tables
                return vision_tables

        return tables

    def _process_raw_matrix(
        self,
        matrix: List[List[Any]],
        page_number: int,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        source: str = "structural",
    ) -> Optional[ExtractedTable]:
        """Clean raw cell matrix, validate sanity, and format into Markdown."""
        cleaned_matrix: List[List[str]] = []
        for row in matrix:
            cleaned_row = [str(c).strip() if c is not None else "" for c in row]
            if any(cleaned_row):
                cleaned_matrix.append(cleaned_row)

        if len(cleaned_matrix) < 2:
            return None

        is_healthy, health_reason = self.check_table_sanity(cleaned_matrix, bbox)

        headers = cleaned_matrix[0]
        # Standardize empty headers
        standardized_headers = [
            h if h.strip() else f"Column_{i+1}"
            for i, h in enumerate(headers)
        ]

        rows = []
        num_cols = len(standardized_headers)
        for r in cleaned_matrix[1:]:
            padded_row = r + [""] * (num_cols - len(r))
            rows.append(padded_row[:num_cols])

        # Generate clean Markdown
        markdown = self.matrix_to_markdown(standardized_headers, rows)

        return ExtractedTable(
            page_number=page_number,
            headers=standardized_headers,
            rows=rows,
            markdown=markdown,
            is_garbled=not is_healthy,
            extraction_source=source,
            bbox=bbox,
            raw_cells=cleaned_matrix,
        )

    def check_table_sanity(
        self,
        cleaned_matrix: List[List[str]],
        bbox: Optional[Tuple[float, float, float, float]] = None,
    ) -> Tuple[bool, str]:
        """
        Sanity check table integrity:
        - At least 1 header + at least 2 real data rows (len >= 3)
        - Column count >= 2
        - Empty header ratio <= 60%
        - Overall empty cell ratio <= 50%
        - Max average characters per cell <= 120 (flags mashed text blocks)
        - Chart dimension & aspect ratio checks (tall height with sparse rows)
        - Mostly numeric or concise short-text data cells in body
        """
        if len(cleaned_matrix) < 3:
            return False, "Less than 2 real data rows"

        col_counts = [len(r) for r in cleaned_matrix]
        max_cols = max(col_counts)
        if max_cols < 2:
            return False, "Single column detected (likely paragraph text)"

        # Header check
        headers = cleaned_matrix[0]
        empty_headers = sum(1 for h in headers if not h.strip())
        if len(headers) > 0 and (empty_headers / len(headers)) > 0.60:
            return False, "High empty header ratio (> 60%)"

        # Overall empty cell check (if more than 50% cells are empty, structural table is broken/sparse)
        total_cells = sum(len(r) for r in cleaned_matrix)
        empty_cells = sum(1 for r in cleaned_matrix for c in r if not c.strip())
        if total_cells > 0 and (empty_cells / total_cells) > 0.50:
            return False, "High empty cell ratio (> 50%)"

        # Mashed text paragraph detection (flags when individual cell > 250 chars or avg > 120 chars)
        total_len = sum(len(c) for r in cleaned_matrix for c in r)
        max_cell_len = max((len(c) for r in cleaned_matrix for c in r), default=0)
        avg_cell_len = total_len / max(1, total_cells)
        if max_cell_len > 250 or avg_cell_len > 120:
            return False, "Mashed text blocks in cells (max > 250 or avg > 120 chars)"

        # Check chart aspect ratio & row height anomalies
        if bbox and len(bbox) == 4:
            tbl_height = max(1.0, float(bbox[3]) - float(bbox[1]))
            num_rows = len(cleaned_matrix)
            avg_row_height = tbl_height / max(1, num_rows)

            if (tbl_height > 100.0 and avg_row_height > 40.0) or (tbl_height > 120.0 and num_rows <= 3):
                return False, f"Chart-like dimensions detected (height={tbl_height:.1f}pt, avg_row_height={avg_row_height:.1f}pt for {num_rows} rows)"

        # Check for row length variance (extreme jaggedness)
        min_cols = min(col_counts)
        if max_cols - min_cols > 4:
            return False, "High row column count variance"

        # Body data cells validation
        data_rows = cleaned_matrix[1:]
        data_cells = [c.strip() for r in data_rows for c in r if c.strip()]
        if not data_cells:
            return False, "No data cells in body rows"

        numeric_or_short_cells = sum(1 for cell in data_cells if re.search(r'[\$€£₹¥\d%]', cell) or len(cell) <= 35)
        if (numeric_or_short_cells / len(data_cells)) < 0.50:
            return False, "Less than 50% numeric or short-text data cells"

        return True, "Healthy"

    def matrix_to_markdown(self, headers: List[str], rows: List[List[str]]) -> str:
        """Convert headers and rows into clean GitHub-flavored Markdown table with stripped placeholder labels."""
        if not headers:
            return ""
        
        # Clean placeholders from headers
        sanitized_headers = clean_table_headers(headers)

        # Clean cell pipes and newlines
        def clean_cell(c: str) -> str:
            cleaned = strip_table_artifacts(str(c))
            return cleaned.replace("|", "\\|").replace("\n", " ").strip()

        clean_h = [clean_cell(h) for h in sanitized_headers]
        lines = [
            "| " + " | ".join(clean_h) + " |",
            "| " + " | ".join(["---"] * len(clean_h)) + " |",
        ]
        for row in rows:
            clean_r = [clean_cell(c) for c in row]
            padded = clean_r + [""] * (len(clean_h) - len(clean_r))
            lines.append("| " + " | ".join(padded[:len(clean_h)]) + " |")

        return "\n".join(lines)

    def _heuristic_looks_like_table(self, text: str) -> bool:
        """Check if raw page text exhibits dense tabular formatting (columns of numbers, currency, percentages)."""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if len(lines) < 4:
            return False
        
        # Count lines with 2 or more numbers or currency/percentage symbols
        tabular_line_count = 0
        for l in lines:
            numbers = re.findall(r"(?:\$|€|£|₹)?\b\d{1,3}(?:,\d{3})*(?:\.\d+)?%?", l)
            if len(numbers) >= 2:
                tabular_line_count += 1

        return tabular_line_count >= 3

    def _has_vision_capability(self) -> bool:
        return bool(self._client or self._legacy_model)

    def _extract_tables_with_gemini_vision(self, fitz_page: fitz.Page, page_number: int) -> List[ExtractedTable]:
        """Render page to image and use Gemini Vision to extract pristine Markdown/JSON tables."""
        try:
            # Render page at 200 DPI for sharp text recognition
            pix = fitz_page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            pil_img = Image.open(io.BytesIO(img_bytes))

            raw_json_str = ""
            model_name = os.getenv("EXTRACTION_MODEL", "gemini-1.5-flash")
            if hasattr(self, "_sdk_type") and self._sdk_type == "google-genai" and self._client:
                response = self._client.models.generate_content(
                    model=model_name,
                    contents=[GEMINI_VISION_TABLE_PROMPT, pil_img],
                )
                raw_json_str = response.text
            elif self._legacy_model:
                response = self._legacy_model.generate_content([GEMINI_VISION_TABLE_PROMPT, pil_img])
                raw_json_str = response.text

            if not raw_json_str:
                return []

            # Parse returned JSON
            cleaned = re.sub(r"^```json\s*", "", raw_json_str.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r"^```\s*$", "", cleaned.strip(), flags=re.MULTILINE)
            data = json.loads(cleaned)

            if isinstance(data, dict):
                data = [data]

            results: List[ExtractedTable] = []
            for item in data:
                headers = [str(h) for h in item.get("headers", [])]
                rows = [[str(c) for c in r] for r in item.get("rows", [])]
                md = item.get("markdown") or self.matrix_to_markdown(headers, rows)
                footnotes = item.get("footnotes", [])

                if headers and rows:
                    results.append(
                        ExtractedTable(
                            page_number=page_number,
                            headers=headers,
                            rows=rows,
                            markdown=md,
                            is_garbled=False,
                            extraction_source="gemini_vision",
                            footnotes=footnotes,
                            raw_cells=[headers] + rows,
                        )
                    )
            return results

        except Exception as e:
            logger.warning(f"Gemini Vision table extraction fallback failed on page {page_number}: {e}")
            return []
