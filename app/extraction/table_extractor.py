"""Specialized table fact extractor preserving structure."""

from __future__ import annotations

import os
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
        if self._model is not None:
            return
        api_key = self.settings.GOOGLE_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return

        try:
            from google import genai
            self._model = genai.Client(api_key=api_key)
            self._sdk_type = "google-genai"
            return
        except Exception:
            pass

        try:
            import google.generativeai as genai_legacy
            genai_legacy.configure(api_key=api_key)
            self._model = genai_legacy.GenerativeModel("gemini-3.6-flash")
            self._sdk_type = "google.generativeai"
            return
        except Exception:
            pass

    async def extract_facts(self, context_window: ContextWindow) -> ExtractionResult:
        """Extract facts from a table context window."""
        result = ExtractionResult()
        self._init_gemini_model()

        text = context_window.full_text or context_window.build()
        if not text:
            return result

        extracted = False
        # 1. Try LLM if configured
        if self._model:
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

        models_to_try = [
            os.getenv("EXTRACTION_MODEL", "gemini-3.6-flash"),
            "gemini-3.6-flash",
            "gemini-flash-latest",
            "gemini-3.5-flash",
        ]

        async with self._semaphore:
            resp_text = None
            if hasattr(self, "_sdk_type") and self._sdk_type == "google-genai" and self._model:
                loop = asyncio.get_event_loop()
                for model_name in models_to_try:
                    try:
                        response = await loop.run_in_executor(
                            None,
                            lambda: self._model.models.generate_content(
                                model=model_name,
                                contents=prompt,
                            )
                        )
                        resp_text = response.text
                        break
                    except Exception:
                        continue
            elif self._model:
                try:
                    if hasattr(self._model, "generate_content_async"):
                        response = await self._model.generate_content_async(prompt)
                        resp_text = response.text
                    else:
                        loop = asyncio.get_event_loop()
                        response = await loop.run_in_executor(
                            None,
                            lambda: self._model.generate_content(prompt)
                        )
                        resp_text = response.text
                except Exception:
                    pass

            if resp_text:
                cleaned = re.sub(r"^```json\s*", "", resp_text.strip(), flags=re.MULTILINE)
                cleaned = re.sub(r"^```\s*$", "", cleaned.strip(), flags=re.MULTILINE)
                # Locate JSON array
                start_idx = cleaned.find("[")
                end_idx = cleaned.rfind("]")
                if start_idx != -1 and end_idx != -1:
                    cleaned = cleaned[start_idx:end_idx + 1]
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
        header_text = getattr(context_window, "document_context_header", "")
        
        entity = (getattr(doc_ctx, "organization", None) or "Organization") if doc_ctx else "Organization"
        if entity == "Organization" and header_text:
            m_org = re.search(r"Organization:\s*([^\n|]+)", header_text)
            if m_org and m_org.group(1).strip() not in ("Organization", "(Please scan this QR Code to view the Prospectus)"):
                entity = m_org.group(1).strip()
            else:
                m_doc = re.search(r"Document:\s*([^\n|]+)", header_text)
                if m_doc:
                    cand = m_doc.group(1).split("-")[0].split("_")[0].strip()
                    if cand and len(cand) > 2 and "scan" not in cand.lower():
                        entity = cand

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
                        metric_name = cells[0].strip()
                        # Skip table titles, footnotes, sources, notes
                        if re.match(r"^(Table\s+\d+|Source:|Note:|Footnote:|1/|2/|3/|Total\s*$)", metric_name, re.IGNORECASE):
                            continue
                        if len(metric_name) < 2 or metric_name.startswith(("[", "(Table")):
                            continue

                        for col_idx, cell_val in enumerate(cells[1:], 1):
                            if cell_val in ("—", "-", "N/A", "n/a", "nil", "", "..."):
                                continue
                            col_header = headers[col_idx] if col_idx < len(headers) else f"Period {col_idx}"
                            if "unlabeled" in col_header.lower() or "column" in col_header.lower():
                                continue

                            num_val = self._parse_numeric(cell_val)
                            fy = col_header if ("20" in col_header or "FY" in col_header.upper()) else None
                            
                            clean_pred = f"{metric_name} ({col_header})" if col_header and not col_header.startswith("Period") else metric_name

                            facts.append(
                                ExtractedFact(
                                    subject=entity,
                                    predicate=clean_pred,
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
                metric_name = str(row_dict[first_key]).strip()
                if re.match(r"^(Table\s+\d+|Source:|Note:|Footnote:|1/|2/|3/)", metric_name, re.IGNORECASE):
                    continue

                for col_name in row_keys[1:]:
                    cell_val = str(row_dict[col_name]).strip()
                    if cell_val in ("—", "-", "N/A", "n/a", "nil", "", "..."):
                        continue
                    if "unlabeled" in col_name.lower() or "column" in col_name.lower():
                        continue

                    num_val = self._parse_numeric(cell_val)
                    fy = col_name if ("20" in col_name or "FY" in col_name.upper()) else None
                    clean_pred = f"{metric_name} ({col_name})" if col_name and not col_name.startswith("Col") else metric_name

                    facts.append(
                        ExtractedFact(
                            subject=entity,
                            predicate=clean_pred,
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
