"""Specialized table fact extractor preserving structure."""

from __future__ import annotations

import re
import json
import asyncio
import time
import logging
from typing import Any

from app.config import get_settings
from app.context.context_window import ContextWindow
from app.extraction.fact_extractor import ExtractedFact, ExtractionResult

logger = logging.getLogger(__name__)

HAS_GENAI = False
try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    try:
        from google import genai
        HAS_GENAI = True
    except ImportError:
        genai = None


TABLE_EXTRACTION_PROMPT = """You are a precision table fact extraction engine.
Extract EVERY factual claim from this table — do not skip anything, even minor line items.
For tables: extract EVERY row, not just totals — sub-line-items matter!
For each row and column intersection:
- Create a distinct atomic fact combining the row metric + column header
- Extract exact numeric values (resolving currency symbols, millions/billions/crore, parentheses for negative numbers)
- Identify the correct unit ("USD", "INR", "%", "employees", etc.) and time period (e.g. "FY2022", "FY2023", "Q3 2024")
- Use the table row or cell context as `source_quote`

Output ONLY a JSON array of objects with fields:
- subject: Entity name
- predicate: Metric / attribute (e.g. "Total Revenue (FY2023)")
- object_value: Value as stated in text
- object_numeric: Parsed numerical float if applicable, else null
- unit: Currency or unit (e.g. "USD", "%", "INR")
- original_text: Exact table row
- evidence_excerpt: Exact cell text
- category: "financial", "operational", "personnel"
- fiscal_year: "FY2023", "FY2024", etc. or null
- fiscal_quarter: "Q1", "Q2", "Q3", "Q4", or null
- currency: "USD", "INR", etc. or null
- confidence: float (0.0 to 1.0)
"""


class TableFactExtractor:
    """
    Specialized extractor for tabular data.
    Combines LLM table understanding with deterministic structural parsing.
    """

    def __init__(self):
        self.settings = get_settings()
        self._semaphore = asyncio.Semaphore(self.settings.MAX_CONCURRENT_LLM_REQUESTS)
        self._model = None

    def _init_gemini_model(self):
        if self._model is None and HAS_GENAI and self.settings.GOOGLE_API_KEY:
            try:
                if hasattr(genai, "configure"):
                    genai.configure(api_key=self.settings.GOOGLE_API_KEY)
                    self._model = genai.GenerativeModel("gemini-1.5-flash")
                elif hasattr(genai, "Client"):
                    self._model = genai.Client(api_key=self.settings.GOOGLE_API_KEY)
            except Exception as e:
                logger.warning(f"Could not init table Gemini model: {e}")

    async def extract_facts(self, context_window: ContextWindow) -> ExtractionResult:
        """Extract facts from a table context window."""
        result = ExtractionResult()
        self._init_gemini_model()

        text = context_window.full_text or context_window.build()
        if not text:
            return result

        extracted = False
        # 1. Try LLM if configured
        if self._model and self.settings.GOOGLE_API_KEY:
            try:
                llm_facts = await self._extract_with_llm(text)
                if llm_facts:
                    result.facts.extend(llm_facts)
                    result.llm_calls += 1
                    extracted = True
            except Exception as e:
                logger.debug(f"Table LLM extraction fallback: {e}")

        # 2. Structural deterministic table extraction
        structural_facts = self._extract_from_table_structure(context_window)
        if structural_facts:
            if not extracted:
                result.facts.extend(structural_facts)
            else:
                existing_keys = {(f.subject.lower(), f.predicate.lower()) for f in result.facts}
                for sf in structural_facts:
                    if (sf.subject.lower(), sf.predicate.lower()) not in existing_keys:
                        result.facts.append(sf)

        return result

    async def _extract_with_llm(self, text: str) -> list[ExtractedFact]:
        facts = []
        prompt = f"{TABLE_EXTRACTION_PROMPT}\n\nTABLE DATA:\n{text}\n\nJSON Output:"

        async with self._semaphore:
            if hasattr(self._model, "generate_content_async"):
                response = await self._model.generate_content_async(prompt)
                resp_text = response.text
            elif hasattr(self._model, "models"):
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self._model.models.generate_content(
                        model=self.settings.EXTRACTION_MODEL,
                        contents=prompt,
                    )
                )
                resp_text = response.text
            else:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self._model.generate_content(prompt)
                )
                resp_text = response.text

            if resp_text:
                cleaned = re.sub(r"^```json\s*", "", resp_text.strip(), flags=re.MULTILINE)
                cleaned = re.sub(r"^```\s*$", "", cleaned.strip(), flags=re.MULTILINE)
                data = json.loads(cleaned)
                if isinstance(data, list):
                    for item in data:
                        fact = self._parse_table_fact(item)
                        if fact:
                            facts.append(fact)
        return facts

    def _extract_from_table_structure(self, context_window: ContextWindow) -> list[ExtractedFact]:
        """Parse structured table blocks into atomic facts."""
        facts = []
        block = getattr(context_window, "target_block", None)
        doc_ctx = getattr(context_window, "doc_context", None)
        entity = (getattr(doc_ctx, "organization", None) or "Organization") if doc_ctx else "Organization"
        currency = (getattr(doc_ctx, "default_currency", None) or "USD") if doc_ctx else "USD"

        # Check structured_content on block
        structured = getattr(block, "structured_content", None) if block else None
        content_text = getattr(block, "content", "") if block else (context_window.primary_evidence or context_window.full_text or "")

        if not structured and content_text:
            # Parse markdown table lines
            lines = [l.strip() for l in content_text.split("\n") if l.strip() and not l.startswith("---")]
            if len(lines) >= 2:
                headers = [h.strip() for h in lines[0].split("|") if h.strip()]
                for row_line in lines[1:]:
                    cells = [c.strip() for c in row_line.split("|") if c.strip()]
                    if len(cells) >= 2:
                        metric_name = cells[0]
                        for col_idx, cell_val in enumerate(cells[1:], 1):
                            if cell_val in ("—", "-", "N/A", "n/a", "nil", ""):
                                continue
                            col_header = headers[col_idx] if col_idx < len(headers) else f"Period {col_idx}"
                            num_val = self._parse_numeric(cell_val)
                            
                            fy = col_header if "20" in col_header or "FY" in col_header.upper() else None
                            
                            facts.append(
                                ExtractedFact(
                                    subject=entity,
                                    predicate=f"{metric_name} ({col_header})",
                                    object_value=cell_val,
                                    object_numeric=num_val,
                                    unit=currency if "$" in cell_val or "$" in col_header else ("%" if "%" in cell_val else None),
                                    original_text=f"{metric_name} | {col_header}: {cell_val}",
                                    evidence_excerpt=cell_val,
                                    category="financial",
                                    fiscal_year=fy,
                                    currency=currency,
                                    confidence=0.95,
                                )
                            )
        elif structured and "rows" in structured:
            rows = structured["rows"]
            for row_dict in rows:
                row_keys = list(row_dict.keys())
                if not row_keys:
                    continue
                first_key = row_keys[0]
                metric_name = str(row_dict[first_key])
                for col_name in row_keys[1:]:
                    cell_val = str(row_dict[col_name]).strip()
                    if cell_val in ("—", "-", "N/A", "n/a", "nil", ""):
                        continue
                    num_val = self._parse_numeric(cell_val)
                    fy = col_name if "20" in col_name or "FY" in col_name.upper() else None
                    facts.append(
                        ExtractedFact(
                            subject=entity,
                            predicate=f"{metric_name} ({col_name})",
                            object_value=cell_val,
                            object_numeric=num_val,
                            unit=currency if "$" in cell_val or "$" in col_name else None,
                            original_text=f"{metric_name} | {col_name}: {cell_val}",
                            evidence_excerpt=cell_val,
                            category="financial",
                            fiscal_year=fy,
                            currency=currency,
                            confidence=0.95,
                        )
                    )

        return facts

    def _parse_table_fact(self, data: dict) -> ExtractedFact | None:
        try:
            subject = str(data.get("subject", "")).strip()
            predicate = str(data.get("predicate", "")).strip()
            val = str(data.get("object_value", "")).strip()
            if not subject or not predicate or not val:
                return None
            if val in ("—", "–", "-", "N/A", "n/a", "NA", "", "nil"):
                return None
            return ExtractedFact(
                subject=subject,
                predicate=predicate,
                object_value=val,
                object_numeric=self._parse_numeric(str(data.get("object_numeric", ""))) or self._parse_numeric(val),
                unit=data.get("unit"),
                original_text=data.get("original_text", f"{predicate}: {val}"),
                evidence_excerpt=data.get("evidence_excerpt", val),
                category=data.get("category", "financial"),
                fiscal_year=data.get("fiscal_year"),
                fiscal_quarter=data.get("fiscal_quarter"),
                scope=data.get("scope"),
                basis=data.get("basis"),
                currency=data.get("currency"),
                confidence=float(data.get("confidence", 0.95)),
            )
        except Exception:
            return None

    def _parse_numeric(self, val_str: str) -> float | None:
        if not val_str:
            return None
        cleaned = val_str.replace("$", "").replace("€", "").replace("£", "").replace("₹", "").replace(",", "").replace("%", "").strip()
        # Handle parenthesized negative values (123) -> -123
        is_negative = False
        if cleaned.startswith("(") and cleaned.endswith(")"):
            is_negative = True
            cleaned = cleaned[1:-1].strip()

        multiplier = 1.0
        if re.search(r"billion|B\b", cleaned, re.IGNORECASE):
            multiplier = 1_000_000_000.0
            cleaned = re.sub(r"billion|B\b", "", cleaned, flags=re.IGNORECASE).strip()
        elif re.search(r"million|M\b", cleaned, re.IGNORECASE):
            multiplier = 1_000_000.0
            cleaned = re.sub(r"million|M\b", "", cleaned, flags=re.IGNORECASE).strip()
        elif re.search(r"thousand|k\b", cleaned, re.IGNORECASE):
            multiplier = 1_000.0
            cleaned = re.sub(r"thousand|k\b", "", cleaned, flags=re.IGNORECASE).strip()

        match = re.search(r"[-+]?\d*\.?\d+", cleaned)
        if match:
            try:
                v = float(match.group()) * multiplier
                return -v if is_negative else v
            except ValueError:
                return None
        return None
