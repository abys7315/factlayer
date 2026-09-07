"""LLM-based & Rule-Assisted Fact Extraction for text blocks."""

from __future__ import annotations

import re
import json
import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Any

from app.config import get_settings
from app.context.context_window import ContextWindow

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


@dataclass
class ExtractedFact:
    """A structured fact extracted from text."""
    subject: str
    predicate: str
    object_value: str
    object_numeric: float | None = None
    unit: str | None = None
    original_text: str = ""
    evidence_excerpt: str = ""
    category: str | None = None
    fiscal_year: str | None = None
    fiscal_quarter: str | None = None
    reporting_period_label: str | None = None
    scope: str | None = None
    geography: str | None = None
    basis: str | None = None
    currency: str | None = None
    is_uncertain: bool = False
    confidence: float = 0.95


@dataclass
class ExtractionResult:
    """Result of an extraction call."""
    facts: list[ExtractedFact] = field(default_factory=list)
    llm_calls: int = 0
    tokens_used: int = 0
    latency_ms: int = 0
    errors: list[str] = field(default_factory=list)


EXTRACTION_SYSTEM_PROMPT = """You are a precision fact extraction system for financial, enterprise, and corporate documents.
Extract EVERY factual claim from this text/table — do not skip anything, even minor line items. Include:
- Every numeric figure with its label, unit, and time period
- Every named entity claim (people, roles, dates of appointment/resignation, subsidiaries)
- Every explicit relationship stated (e.g. "X is a subsidiary of Y", "Company A acquired Company B")
- Footnote disclosures, accounting basis (GAAP vs Non-GAAP), and period definitions

Err on the side of extracting too much rather than too little — a downstream system will filter noise later.
For tables: extract EVERY row, not just totals — sub-line-items matter!

Output ONLY a JSON array with objects containing:
- subject: Entity name (e.g. Acme Technologies Inc.)
- predicate: Attribute/Metric (e.g. Total Revenue, GAAP Net Income, Operating Margin, Headcount, Chief Executive Officer)
- object_value: Value as stated in text (e.g. $100,000,000, 450 employees, John Smith)
- object_numeric: Parsed numerical float if applicable (e.g. 100000000.0, 450.0)
- unit: USD, %, employees, etc.
- currency: USD, EUR, INR, etc.
- original_text: Exact verbatim sentence quote from text
- evidence_excerpt: Exact concise excerpt
- category: financial, personnel, governance, operational, legal
- fiscal_year: FY2023, FY2024, etc. or null
- fiscal_quarter: Q1, Q2, Q3, Q4, or null
- scope: Consolidated, Segment, Global, etc.
- basis: GAAP, Non-GAAP, etc.
- confidence: 0.0 to 1.0

### Few-Shot Example 1 (Financial Metrics):
Input:
"Acme Technologies Inc. achieved total full-year revenue of $100,000,000 ($100M USD) for the fiscal year ended December 31, 2023 with GAAP Net Income of $18,000,000."
Output:
[
  {
    "subject": "Acme Technologies Inc.",
    "predicate": "Total Revenue",
    "object_value": "$100,000,000",
    "object_numeric": 100000000.0,
    "unit": "USD",
    "currency": "USD",
    "fiscal_year": "FY2023",
    "basis": "GAAP",
    "scope": "Consolidated",
    "category": "financial",
    "original_text": "Acme Technologies Inc. achieved total full-year revenue of $100,000,000 ($100M USD) for the fiscal year ended December 31, 2023 with GAAP Net Income of $18,000,000.",
    "evidence_excerpt": "total full-year revenue of $100,000,000 ($100M USD) for the fiscal year ended December 31, 2023",
    "confidence": 0.99
  },
  {
    "subject": "Acme Technologies Inc.",
    "predicate": "GAAP Net Income",
    "object_value": "$18,000,000",
    "object_numeric": 18000000.0,
    "unit": "USD",
    "currency": "USD",
    "fiscal_year": "FY2023",
    "basis": "GAAP",
    "scope": "Consolidated",
    "category": "financial",
    "original_text": "Acme Technologies Inc. achieved total full-year revenue of $100,000,000 ($100M USD) for the fiscal year ended December 31, 2023 with GAAP Net Income of $18,000,000.",
    "evidence_excerpt": "GAAP Net Income of $18,000,000",
    "confidence": 0.99
  }
]

### Few-Shot Example 2 (Leadership Transition):
Input:
"Chief Executive Officer: John Smith (appointed July 2024, succeeding Jane Doe)."
Output:
[
  {
    "subject": "Acme Technologies Inc.",
    "predicate": "Chief Executive Officer",
    "object_value": "John Smith",
    "object_numeric": null,
    "unit": null,
    "currency": null,
    "fiscal_year": "FY2024",
    "category": "governance",
    "original_text": "Chief Executive Officer: John Smith (appointed July 2024, succeeding Jane Doe).",
    "evidence_excerpt": "Chief Executive Officer: John Smith (appointed July 2024, succeeding Jane Doe)",
    "confidence": 0.98
  }
]
"""


class TextFactExtractor:
    """
    Fact extraction engine supporting both LLM (Gemini) and
    high-precision deterministic pattern extractors.
    """

    def __init__(self):
        self.settings = get_settings()
        self._semaphore = asyncio.Semaphore(self.settings.MAX_CONCURRENT_LLM_REQUESTS)
        self._model = None
        self._sdk_type = None

    def _init_gemini_model(self):
        if self._model is not None:
            return

        api_key = self.settings.GOOGLE_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return

        # Attempt 1: google.genai Client (new SDK)
        try:
            from google import genai
            self._model = genai.Client(api_key=api_key)
            self._sdk_type = "google-genai"
            return
        except Exception:
            pass

        # Attempt 2: google.generativeai (legacy SDK)
        try:
            import google.generativeai as genai_legacy
            genai_legacy.configure(api_key=api_key)
            model_name = os.getenv("EXTRACTION_MODEL", "gemini-flash-latest")
            self._model = genai_legacy.GenerativeModel(model_name)
            self._sdk_type = "google.generativeai"
            return
        except Exception:
            pass

    async def extract_facts(self, context_windows: list[ContextWindow]) -> ExtractionResult:
        """Extract facts from a batch of context windows."""
        result = ExtractionResult()
        self._init_gemini_model()

        for window in context_windows:
            # Prefer primary_evidence for text extraction; full_text for LLM context
            evidence_text = getattr(window, "primary_evidence", "") or getattr(window, "full_text", "")
            if not evidence_text or len(evidence_text.strip()) < 10:
                continue

            extracted = False
            # 1. Try LLM if configured and available
            if self._model:
                try:
                    full_prompt_text = window.full_text or window.build()
                    llm_facts = await self._extract_with_llm(full_prompt_text, window)
                    if llm_facts:
                        result.facts.extend(llm_facts)
                        result.llm_calls += 1
                        extracted = True
                except Exception as e:
                    logger.debug(f"LLM extraction fallback to rule extractor: {e}")

            # 2. Rule/Pattern Extractor fallback or booster (on primary evidence, not headers)
            rule_facts = self._extract_with_rules(evidence_text, window)
            if rule_facts:
                if not extracted:
                    result.facts.extend(rule_facts)
                else:
                    existing_keys = {(f.subject.lower(), f.predicate.lower(), str(f.object_value).lower()) for f in result.facts}
                    for rf in rule_facts:
                        key = (rf.subject.lower(), rf.predicate.lower(), str(rf.object_value).lower())
                        if key not in existing_keys:
                            result.facts.append(rf)

        return result

    async def _extract_with_llm(self, text: str, window: ContextWindow) -> list[ExtractedFact]:
        """Extract facts using Gemini LLM."""
        facts = []
        prompt = f"{EXTRACTION_SYSTEM_PROMPT}\n\nEVIDENCE:\n{text}\n\nJSON Output:"

        models_to_try = [
            os.getenv("EXTRACTION_MODEL", "gemini-flash-latest"),
            "gemini-2.5-flash",
            "gemini-flash-latest",
            "gemini-2.0-flash",
        ]

        async with self._semaphore:
            resp_text = None
            if self._sdk_type == "google-genai" and self._model:
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
                        fact = self._parse_fact_dict(item, text)
                        if fact:
                            facts.append(fact)
        return facts

    def _extract_with_rules(self, text: str, window: ContextWindow) -> list[ExtractedFact]:
        """High-precision deterministic extraction for financial, corporate, and operational facts."""
        facts = []

        # Extract entity and currency from document_context_header
        entity = "Organization"
        currency = "USD"
        header = getattr(window, "document_context_header", "")
        if header:
            m = re.search(r"Organization:\s*([^\n|]+)", header)
            if m and m.group(1).strip() not in ("Organization", "(Please scan this QR Code to view the Prospectus)"):
                entity = m.group(1).strip()
            else:
                m_doc = re.search(r"Document:\s*([^\n|]+)", header)
                if m_doc:
                    doc_cand = m_doc.group(1).split("-")[0].split("(")[0].strip()
                    if doc_cand and "scan" not in doc_cand.lower():
                        entity = doc_cand

            m_curr = re.search(r"Currency:\s*([A-Z]{3})", header)
            if m_curr:
                currency = m_curr.group(1).strip()

        if entity == "Organization":
            m_org = re.search(r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)*(?:\s+(?:Corp|Inc|Ltd|LLC|Corporation|Enterprises|Technologies|Bank|Financial|Holdings|Group)))\b", text)
            if m_org:
                entity = m_org.group(1).strip()

        # Find fiscal year / period in text
        fy_match = re.search(r"\b(FY\s*20\d\d|20\d\d\s*Annual|20\d\d)\b", text, re.IGNORECASE)
        fiscal_year = fy_match.group(1).replace(" ", "").upper() if fy_match else None

        scope = "Consolidated" if "consolidated" in text.lower() else "Segment"
        basis = "Non-GAAP" if "non-gaap" in text.lower() else ("GAAP" if "gaap" in text.lower() else "Reported")

        # Sentence parsing — filter out any metadata header lines
        sentences = []
        for raw_line in text.split("\n"):
            line_clean = raw_line.strip()
            if not line_clean or line_clean.startswith(("ORGANIZATION:", "DOCUMENT:", "CONTEXT:", "PRIMARY EVIDENCE:", "SECTION:", "PAGE:")):
                continue
            for s in re.split(r"(?<=[.?!])\s+", line_clean):
                s_strip = s.strip()
                if len(s_strip) >= 15:
                    sentences.append(s_strip)

        for sentence in sentences:
            # Financial metrics
            metric_patterns = [
                (r"(revenue|total revenue|sales|net sales)\s+(?:was|were|of|reached|is|totaled)\s+([$€£₹]?\s*[\d,.]+\s*(?:billion|million|trillion|crore|lakh|B|M|k)?)", "Revenue", "financial"),
                (r"(net income|net profit|net loss)\s+(?:was|were|of|reached|is|totaled)\s+([$€£₹]?\s*[\d,.]+\s*(?:billion|million|trillion|crore|lakh|B|M|k)?)", "Net Income", "financial"),
                (r"(operating income|operating profit|operating cash flow)\s+(?:was|were|of|reached|is|totaled)\s+([$€£₹]?\s*[\d,.]+\s*(?:billion|million|trillion|crore|lakh|B|M|k)?)", "Operating Income", "financial"),
                (r"(gross profit|gross margin)\s+(?:was|were|of|reached|is|totaled)\s+([$€£₹]?\s*[\d,.]+\s*(?:billion|million|%|percent)?)", "Gross Profit", "financial"),
                (r"(earnings per share|eps|diluted eps)\s+(?:was|were|of|reached|is|totaled)\s+([$€£₹]?\s*[\d,.]+)", "EPS", "financial"),
                (r"(ebitda|adjusted ebitda)\s+(?:was|were|of|reached|is|totaled)\s+([$€£₹]?\s*[\d,.]+\s*(?:billion|million|B|M)?)", "EBITDA", "financial"),
                (r"(headcount|employees|full-time employees|workforce)\s+(?:was|were|of|reached|is|totaled)\s+([\d,]+(?:\s*employees)?)", "Headcount", "operational"),
                (r"(active users|monthly active users|subscribers|customers)\s+(?:was|were|of|reached|is|totaled)\s+([\d,.]+\s*(?:million|billion|M|B)?)", "Customer Base", "operational"),
            ]

            for regex, pred_name, cat in metric_patterns:
                match = re.search(regex, sentence, re.IGNORECASE)
                if match:
                    val_text = match.group(2).strip()
                    num_val = self._parse_numeric(val_text)
                    unit = "%" if "%" in val_text else currency

                    facts.append(
                        ExtractedFact(
                            subject=entity,
                            predicate=pred_name,
                            object_value=val_text,
                            object_numeric=num_val,
                            unit=unit,
                            original_text=sentence,
                            evidence_excerpt=sentence,
                            category=cat,
                            fiscal_year=fiscal_year,
                            scope=scope,
                            basis=basis,
                            currency=currency,
                            confidence=0.95,
                        )
                    )

            # Executive / Governance
            gov_patterns = [
                (r"(?:appointed|named|promoted)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+as\s+(Chief Executive Officer|CEO|CFO|COO|President|Director|Chairman)", "Chief Executive Officer", "governance"),
                (r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(?:serves as|is the)\s+(CEO|Chief Executive Officer|CFO|President)", "Executive Officer", "governance"),
            ]
            for regex, pred_name, cat in gov_patterns:
                match = re.search(regex, sentence)
                if match:
                    person = match.group(1).strip()
                    role = match.group(2).strip()
                    facts.append(
                        ExtractedFact(
                            subject=entity,
                            predicate=role,
                            object_value=person,
                            original_text=sentence,
                            evidence_excerpt=sentence,
                            category=cat,
                            fiscal_year=fiscal_year,
                            confidence=0.95,
                        )
                    )

        return facts

    def _parse_fact_dict(self, data: dict, full_text: str) -> ExtractedFact | None:
        """Validate and parse a dictionary into ExtractedFact."""
        try:
            subject = str(data.get("subject", "")).strip()
            predicate = str(data.get("predicate", "")).strip()
            val = str(data.get("object_value", "")).strip()
            if not subject or not predicate or not val:
                return None
            return ExtractedFact(
                subject=subject,
                predicate=predicate,
                object_value=val,
                object_numeric=self._parse_numeric(str(data.get("object_numeric", ""))) or self._parse_numeric(val),
                unit=data.get("unit"),
                original_text=data.get("original_text", full_text[:200]),
                evidence_excerpt=data.get("evidence_excerpt", val),
                category=data.get("category", "General"),
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
        """Parse numeric values including billion/million multipliers."""
        if not val_str:
            return None
        cleaned = val_str.replace("$", "").replace("€", "").replace("£", "").replace("₹", "").replace(",", "").replace("%", "").strip()
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
                return float(match.group()) * multiplier
            except ValueError:
                return None
        return None
