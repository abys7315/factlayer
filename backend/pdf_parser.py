"""PDF Parser using PyMuPDF (fitz) and pdfplumber with TableParser integration.

Extracts text WITH exact bounding boxes at extraction time (no re-searching for strings later = no misaligned highlights).
"""

from __future__ import annotations
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import fitz  # PyMuPDF

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from backend.table_parser import TableParser, ExtractedTable
from backend.table_cleaner import strip_table_artifacts, clean_table_headers

logger = logging.getLogger(__name__)


# ============================================================
# FIX 1: bbox-at-extraction-time (backend/pdf_parser.py)
# ============================================================
#
# PROBLEM: extracting text first, then later calling page.search_for(text)
# to find its bbox finds the WRONG occurrence when similar text appears
# multiple times on a page (e.g. repeated table headers). This is why your
# highlight boxes land on the wrong table.
#
# FIX: get text AND bbox in the SAME pass, at the word/line level, and
# carry both through the pipeline together. Never re-search afterward.

def extract_page_chunks_with_bbox(pdf_path: str, page_num: int, line_gap_px: float = 3.0):
    """
    Extract text from a page as line-level chunks, each with its exact
    bounding box captured at extraction time.

    Returns a list of dicts:
        {
            "text": str,
            "bbox": (x0, y0, x1, y1),   # PDF coordinate space
            "page_number": int,         # 1-indexed, matches what the user sees
        }
    """
    doc = fitz.open(pdf_path)
    page = doc[page_num - 1]  # fitz is 0-indexed internally

    # get_text("words") returns (x0, y0, x1, y1, word, block_no, line_no, word_no)
    words = page.get_text("words")
    doc.close()

    if not words:
        return []

    # Group words into lines using (block_no, line_no) — this keeps the
    # bbox tightly coupled to the exact text it belongs to, so there is
    # nothing to "re-find" downstream.
    lines = {}
    for x0, y0, x1, y1, word, block_no, line_no, word_no in words:
        key = (block_no, line_no)
        if key not in lines:
            lines[key] = {"words": [], "x0": x0, "y0": y0, "x1": x1, "y1": y1}
        entry = lines[key]
        entry["words"].append((word_no, word))
        entry["x0"] = min(entry["x0"], x0)
        entry["y0"] = min(entry["y0"], y0)
        entry["x1"] = max(entry["x1"], x1)
        entry["y1"] = max(entry["y1"], y1)

    chunks = []
    for (block_no, line_no), entry in sorted(lines.items()):
        text = " ".join(w for _, w in sorted(entry["words"]))
        chunks.append({
            "text": text,
            "bbox": (entry["x0"], entry["y0"], entry["x1"], entry["y1"]),
            "page_number": page_num,
        })
    return chunks


def group_chunks_into_blocks(chunks: list, y_gap_threshold: float = 12.0):
    """
    Merge adjacent line-chunks into paragraph/table-row-sized blocks for
    feeding to the LLM, while keeping a MERGED bbox that spans all the
    lines it came from. This is what you pass to fact extraction — the
    bbox travels with the text as one unit, so there's no disconnect
    between "what the LLM read" and "where it is on the page."
    """
    if not chunks:
        return []

    blocks = []
    current = {
        "text": chunks[0]["text"],
        "bbox": list(chunks[0]["bbox"]),
        "page_number": chunks[0]["page_number"],
    }

    for prev, cur in zip(chunks, chunks[1:]):
        gap = cur["bbox"][1] - prev["bbox"][3]  # y0 of cur - y1 of prev
        if gap <= y_gap_threshold:
            current["text"] += " " + cur["text"]
            current["bbox"][0] = min(current["bbox"][0], cur["bbox"][0])
            current["bbox"][1] = min(current["bbox"][1], cur["bbox"][1])
            current["bbox"][2] = max(current["bbox"][2], cur["bbox"][2])
            current["bbox"][3] = max(current["bbox"][3], cur["bbox"][3])
        else:
            blocks.append(current)
            current = {
                "text": cur["text"],
                "bbox": list(cur["bbox"]),
                "page_number": cur["page_number"],
            }
    blocks.append(current)
    return blocks


class PDFParser:
    """Extract structured text chunks and clean tables with page numbers and exact bboxes from PDF files."""

    def __init__(self, chunk_by_page: bool = True, max_chars_per_chunk: int = 12000):
        self.chunk_by_page = chunk_by_page
        self.max_chars_per_chunk = max_chars_per_chunk
        self.table_parser = TableParser()

    def parse_pdf(self, pdf_path: str | Path) -> Dict[str, Any]:
        """
        Parse a PDF file and return document metadata, structured tables, and chunks with exact bboxes.
        
        Returns:
            Dict containing:
                - "page_count": Total number of pages
                - "chunks": List of dicts with {"page_number", "text", "chunk_id", "tables_count", "tables", "bbox"}
                - "tables": List of all ExtractedTable objects
                - "full_text": Complete text of the document with clean Markdown tables
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        doc = fitz.open(str(pdf_path))
        page_count = len(doc)
        chunks: List[Dict[str, Any]] = []
        full_text_parts: List[str] = []
        all_tables: List[ExtractedTable] = []

        # ── Pre-pass: Detect Document-Wide Repeated Boilerplate Lines ──────────
        boilerplate_lines = self._detect_document_boilerplate(doc)

        chunk_id = 0
        for page_idx in range(page_count):
            page_number = page_idx + 1
            page = doc[page_idx]
            page_rect = page.rect
            page_w, page_h = float(page_rect.width), float(page_rect.height)
            raw_page_text = page.get_text("text").strip()

            # Filter out boilerplate lines from page narrative
            page_text = self._filter_boilerplate(raw_page_text, boilerplate_lines)

            # 1. Structural Table Extraction with Sanity Check & Gemini Vision Fallback
            page_tables = self.table_parser.extract_tables_from_page(
                fitz_page=page,
                page_number=page_number,
            )
            all_tables.extend(page_tables)

            # Format extracted tables as clean Markdown sections
            table_markdown_blocks = []
            for i, tbl in enumerate(page_tables, 1):
                tbl_title = f"### Table {i} (Page {page_number}) [{tbl.extraction_source.upper()}]"
                table_block = f"{tbl_title}\n{tbl.markdown}"
                if tbl.footnotes:
                    table_block += "\n" + "\n".join(f"* {fn}" for fn in tbl.footnotes)
                table_markdown_blocks.append(table_block)

            # OCR Fallback only if page text is truly empty and page contains embedded images
            if (not page_text or len(page_text) < 15) and len(page.get_images()) > 0:
                try:
                    ocr_page = page.get_textpage_ocr(language="eng", dpi=150)
                    ocr_text = ocr_page.extractText().strip()
                    ocr_filtered = self._filter_boilerplate(ocr_text, boilerplate_lines)
                    if ocr_filtered and len(ocr_filtered) > len(page_text):
                        page_text = ocr_filtered
                except Exception:
                    try:
                        import pytesseract
                        from PIL import Image
                        import io
                        pix = page.get_pixmap(dpi=150)
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        tess_text = pytesseract.image_to_string(img).strip()
                        tess_filtered = self._filter_boilerplate(tess_text, boilerplate_lines)
                        if tess_filtered and len(tess_filtered) > len(page_text):
                            page_text = tess_filtered
                    except Exception:
                        pass

            # Combine page narrative text with clean structured table markdown
            combined_page_text_parts = []
            if page_text:
                combined_page_text_parts.append(page_text)
            if table_markdown_blocks:
                combined_page_text_parts.append("\n\n".join(table_markdown_blocks))

            combined_page_content = "\n\n".join(combined_page_text_parts).strip()
            if not combined_page_content:
                continue

            full_text_parts.append(f"--- Page {page_number} ---\n{combined_page_content}")

            # Extract line-level chunks with bbox for this page
            page_line_chunks = []
            words = page.get_text("words")
            if words:
                lines = {}
                for x0, y0, x1, y1, word, block_no, line_no, word_no in words:
                    key = (block_no, line_no)
                    if key not in lines:
                        lines[key] = {"words": [], "x0": x0, "y0": y0, "x1": x1, "y1": y1}
                    entry = lines[key]
                    entry["words"].append((word_no, word))
                    entry["x0"] = min(entry["x0"], x0)
                    entry["y0"] = min(entry["y0"], y0)
                    entry["x1"] = max(entry["x1"], x1)
                    entry["y1"] = max(entry["y1"], y1)

                for (block_no, line_no), entry in sorted(lines.items()):
                    line_txt = " ".join(w for _, w in sorted(entry["words"]))
                    # Filter out boilerplate
                    if line_txt.lower().strip() not in boilerplate_lines:
                        page_line_chunks.append({
                            "text": line_txt,
                            "bbox": (entry["x0"], entry["y0"], entry["x1"], entry["y1"]),
                            "page_number": page_number,
                        })

            grouped_blocks = group_chunks_into_blocks(page_line_chunks)
            page_bbox = (0.0, 0.0, page_w, page_h)
            if grouped_blocks:
                page_bbox = (
                    min(b["bbox"][0] for b in grouped_blocks),
                    min(b["bbox"][1] for b in grouped_blocks),
                    max(b["bbox"][2] for b in grouped_blocks),
                    max(b["bbox"][3] for b in grouped_blocks),
                )

            # If chunk_by_page is True (default) or page fits in context window, keep complete page unified
            if self.chunk_by_page or len(combined_page_content) <= self.max_chars_per_chunk:
                chunks.append({
                    "chunk_id": chunk_id,
                    "page_number": page_number,
                    "text": combined_page_content,
                    "tables_count": len(page_tables),
                    "tables": page_tables,
                    "bbox": page_bbox,
                    "blocks": grouped_blocks,
                })
                chunk_id += 1
            else:
                # Structural section chunking
                if grouped_blocks:
                    for gb in grouped_blocks:
                        if len(gb["text"].strip()) < 15:
                            continue
                        chunks.append({
                            "chunk_id": chunk_id,
                            "page_number": page_number,
                            "text": gb["text"],
                            "tables_count": 0,
                            "tables": [],
                            "bbox": tuple(gb["bbox"]),
                            "blocks": [gb],
                        })
                        chunk_id += 1
                for i, tbl in enumerate(page_tables, 1):
                    tbl_title = f"### Table {i} (Page {page_number}) [{tbl.extraction_source.upper()}]"
                    tbl_content = f"{tbl_title}\n{tbl.markdown}"
                    chunks.append({
                        "chunk_id": chunk_id,
                        "page_number": page_number,
                        "text": tbl_content,
                        "tables_count": 1,
                        "tables": [tbl],
                        "bbox": tbl.bbox or page_bbox,
                        "blocks": [],
                    })
                    chunk_id += 1

        doc.close()

        return {
            "page_count": page_count,
            "chunks": chunks,
            "tables": all_tables,
            "full_text": "\n\n".join(full_text_parts),
        }

    def _detect_document_boilerplate(self, doc: fitz.Document) -> set[str]:
        """
        Detect repeated headers, footers, disclaimers, and watermarks across pages.
        A multi-word line appearing on >5% of pages (or >= 3 pages in short docs) is considered boilerplate.
        """
        boilerplate = set()
        page_count = len(doc)
        if page_count < 2:
            return boilerplate

        line_page_counts: dict[str, int] = {}
        for page in doc:
            page_text = page.get_text("text") or ""
            unique_lines_on_page = set()
            for raw_line in page_text.splitlines():
                line = raw_line.strip()
                if not line or len(line) < 3:
                    continue
                # Normalize line
                line_clean = re.sub(r"\s+", " ", line).lower()
                unique_lines_on_page.add(line_clean)

            for line_clean in unique_lines_on_page:
                line_page_counts[line_clean] = line_page_counts.get(line_clean, 0) + 1

        threshold = max(3, int(page_count * 0.05))
        for line_clean, count in line_page_counts.items():
            words = line_clean.split()
            # If multi-word line appears on >5% of pages or is a known boilerplate pattern
            if count >= threshold and len(words) >= 2:
                # Do not filter out common financial line items like 'Total Revenue', 'Net Income'
                if line_clean not in {"total revenue", "net income", "operating income", "total equity", "cash flows", "balance sheet"}:
                    boilerplate.add(line_clean)

        return boilerplate

    def _filter_boilerplate(self, text: str, boilerplate_lines: set[str]) -> str:
        """Strip boilerplate headers, footers, disclaimers, and QR codes from text."""
        if not text:
            return ""

        filtered_lines = []
        for line in text.split("\n"):
            line_s = line.strip()
            if not line_s:
                continue

            line_clean = re.sub(r"\s+", " ", line_s).lower()

            # Check explicit static boilerplate patterns
            if any(pat in line_clean for pat in [
                "please scan this qr code",
                "draft red herring prospectus",
                "red herring prospectus",
                "for private circulation only",
                "strictly confidential",
            ]):
                continue

            # Check dynamic document-wide boilerplate lines
            if line_clean in boilerplate_lines:
                continue

            # Filter standalone page number lines like "Page 12 of 100" or just "12"
            if re.match(r"^(page\s+)?\d+(\s+of\s+\d+)?$", line_clean):
                continue

            filtered_lines.append(line_s)

        return "\n".join(filtered_lines).strip()
