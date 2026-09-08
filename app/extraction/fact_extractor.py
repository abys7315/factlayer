"""LLM-based & Rule-Assisted Fact Extraction for text blocks."""

from __future__ import annotations

import os
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


EXTRACTION_SYSTEM_PROMPT = """You are a precision fact extraction engine for financial filings, statutory reports (10-K, 10-Q, 8-K, IMF Article IV Reports, Annual Reports, Press Releases), and corporate disclosures.

Your mission is to extract EVERY verifiable atomic factual claim from the given text/table with zero hallucination.

### CRITICAL EXTRACTION RULES:
1. ATOMIC DECOMPOSITION: Decompose compound sentences into distinct, self-contained atomic facts.
   - Example: "Acme grew revenue 14% to $100M in FY23 while Net Income reached $18M" -> 3 distinct facts: Total Revenue ($100M), Revenue Growth Rate (14%), and Net Income ($18M).
2. EXHAUSTIVE COVERAGE:
   - Extract EVERY numeric metric, sub-line item, ratio, percentage, headcount figure, date, and executive appointment.
   - For tables: extract EVERY row and column intersection. Do not omit sub-line items or footnote qualifications.
3. FINANCIAL PRECISION:
   - Handle multiplier scales ("in millions", "in billions", "in thousands", "₹ crore", "₹ lakh", "bps").
   - Handle negative values in parentheses: e.g. `(15.2)` -> negative value `-15.2`.
   - Identify ISO currency codes: USD, EUR, INR, GBP, JPY, CAD, AUD, etc.
   - Mark unit: USD, EUR, INR, %, bps, employees, shares, metric tons, etc.
4. ACCOUNTING BASIS & SCOPE:
   - Basis: "GAAP", "Non-GAAP", "Adjusted", "IFRS", "Ind AS", "Pro-forma", "As-Reported", "Restated".
   - Scope: "Consolidated", "Standalone", "Segment: <Name>", "Geographic: <Region>", "Constant Currency".
   - Fiscal Period: "FY2023", "FY2024", "Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024", "H1 2024", "As of Dec 31, 2023", "Trailing 12 Months (TTM)".
5. GROUNDING & VERBATIM QUOTING:
   - `original_text`: The exact verbatim sentence from the source text containing this fact.
   - `evidence_excerpt`: The concise, exact phrase supporting the fact.
6. NO BOILERPLATE:
   - Do NOT extract page footers, disclaimer boilerplate, or copyright marks as facts.

Output ONLY a JSON array of objects with the following schema:
[
  {
    "subject": "Entity name (e.g. Acme Technologies Inc. or India)",
    "predicate": "Attribute / Metric (e.g. Total Revenue, Real GDP Growth, GAAP Net Income, Chief Executive Officer)",
    "object_value": "Formatted value as stated (e.g. $100,000,000, 6.5%, John Smith)",
    "object_numeric": 100000000.0, // Numerical float or null
    "unit": "USD", // Unit or currency code
    "currency": "USD", // ISO currency code or null
    "fiscal_year": "FY2023", // Fiscal year or period string
    "fiscal_quarter": null, // Q1, Q2, Q3, Q4, or null
    "basis": "GAAP", // GAAP, Non-GAAP, Adjusted, Ind AS, or null
    "scope": "Consolidated", // Consolidated, Segment, Constant Currency, or null
    "category": "financial", // "financial" | "governance" | "operational" | "regulatory" | "macroeconomic" | "legal"
    "original_text": "Exact verbatim sentence from the document text.",
    "evidence_excerpt": "Exact concise excerpt.",
    "confidence": 0.99
  }
]

### Few-Shot Example 1 (Income Statement & Accounting Standards):
Input:
"Acme Technologies Inc. achieved total consolidated full-year revenue of $100,000,000 ($100M USD) for the fiscal year ended December 31, 2023. GAAP Net Income was $18,000,000, while Non-GAAP Adjusted EBITDA reached $24,500,000."
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
    "original_text": "Acme Technologies Inc. achieved total consolidated full-year revenue of $100,000,000 ($100M USD) for the fiscal year ended December 31, 2023.",
    "evidence_excerpt": "total consolidated full-year revenue of $100,000,000 ($100M USD) for the fiscal year ended December 31, 2023",
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
    "original_text": "GAAP Net Income was $18,000,000, while Non-GAAP Adjusted EBITDA reached $24,500,000.",
    "evidence_excerpt": "GAAP Net Income was $18,000,000",
    "confidence": 0.99
  },
  {
    "subject": "Acme Technologies Inc.",
    "predicate": "Adjusted EBITDA",
    "object_value": "$24,500,000",
    "object_numeric": 24500000.0,
    "unit": "USD",
    "currency": "USD",
    "fiscal_year": "FY2023",
    "basis": "Non-GAAP",
    "scope": "Consolidated",
    "category": "financial",
    "original_text": "GAAP Net Income was $18,000,000, while Non-GAAP Adjusted EBITDA reached $24,500,000.",
    "evidence_excerpt": "Non-GAAP Adjusted EBITDA reached $24,500,000",
    "confidence": 0.99
  }
]

### Few-Shot Example 2 (Executive Leadership & Corporate Governance):
Input:
"Executive Leadership: John Smith was appointed Chief Executive Officer in July 2024, succeeding Jane Doe who resigned as CEO effective June 30, 2024."
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
    "basis": null,
    "scope": "Corporate",
    "category": "governance",
    "original_text": "Executive Leadership: John Smith was appointed Chief Executive Officer in July 2024, succeeding Jane Doe who resigned as CEO effective June 30, 2024.",
    "evidence_excerpt": "John Smith was appointed Chief Executive Officer in July 2024",
    "confidence": 0.99
  },
  {
    "subject": "Jane Doe",
    "predicate": "Resignation as Chief Executive Officer",
    "object_value": "June 30, 2024",
    "object_numeric": null,
    "unit": null,
    "currency": null,
    "fiscal_year": "FY2024",
    "basis": null,
    "scope": "Corporate",
    "category": "governance",
    "original_text": "Executive Leadership: John Smith was appointed Chief Executive Officer in July 2024, succeeding Jane Doe who resigned as CEO effective June 30, 2024.",
    "evidence_excerpt": "Jane Doe who resigned as CEO effective June 30, 2024",
    "confidence": 0.99
  }
]

### Few-Shot Example 3 (Macroeconomic & Statutory Reports):
Input:
"India's real GDP growth is projected at 6.5 percent in FY2024/25, supported by strong public investment, while headline inflation is expected to moderate to 4.5 percent."
Output:
[
  {
    "subject": "India",
    "predicate": "Real GDP Growth Rate",
    "object_value": "6.5%",
    "object_numeric": 6.5,
    "unit": "%",
    "currency": null,
    "fiscal_year": "FY2024/25",
    "basis": "Reported",
    "scope": "National",
    "category": "macroeconomic",
    "original_text": "India's real GDP growth is projected at 6.5 percent in FY2024/25, supported by strong public investment, while headline inflation is expected to moderate to 4.5 percent.",
    "evidence_excerpt": "real GDP growth is projected at 6.5 percent in FY2024/25",
    "confidence": 0.99
  },
  {
    "subject": "India",
    "predicate": "Headline Inflation Rate",
    "object_value": "4.5%",
    "object_numeric": 4.5,
    "unit": "%",
    "currency": null,
    "fiscal_year": "FY2024/25",
    "basis": "Reported",
    "scope": "National",
    "category": "macroeconomic",
    "original_text": "India's real GDP growth is projected at 6.5 percent in FY2024/25, supported by strong public investment, while headline inflation is expected to moderate to 4.5 percent.",
    "evidence_excerpt": "headline inflation is expected to moderate to 4.5 percent",
    "confidence": 0.99
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
            os.getenv("EXTRACTION_MODEL", "gemini-3.6-flash"),
            "gemini-3.6-flash",
            "gemini-flash-latest",
            "gemini-3.5-flash",
            "gemini-2.5-flash-lite",
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

        # Find fiscal year / period in text (prioritize full year spans like 2024-25 or FY2024-25)
        fy_match = re.search(r"\b(FY\s*20\d\d(?:-\d\d)?|20\d\d-\d\d|20\d\d\s*Annual|20\d\d)\b", text, re.IGNORECASE)
        fiscal_year = None
        if fy_match:
            fy_clean = fy_match.group(1).replace(" ", "").upper()
            fiscal_year = f"FY{fy_clean}" if not fy_clean.startswith("FY") and ":" not in fy_clean else fy_clean

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
            sentence_entity = entity

            # Detect sentence-specific entities/subjects
            m_subj = re.search(
                r"\b(Aggregate\s+demand(?:\s*[-–—]\s*measured\s+by\s+GDP(?:\s+at\s+constant\s+prices)?)?|"
                r"GDP\s+at\s+constant\s+prices|Real\s+GDP|Nominal\s+GDP|Gross\s+Domestic\s+Product|"
                r"Headline\s+inflation|Food\s+inflation|Core\s+disinflation|Core\s+inflation|Fuel\s+deflation|"
                r"Tax\s+receipts\s+of\s+both\s+central\s+and\s+state\s+governments|Tax\s+receipts|Capital\s+expenditure|"
                r"Central\s+and\s+state\s+governments|Fiscal\s+consolidation|Fiscal\s+deficit|Current\s+account\s+deficit|"
                r"Credit\s+growth|Deposit\s+growth|Certificates\s+of\s+deposit(?:\s*\(CDs\))?|Issuances\s+of\s+certificates\s+of\s+deposit|"
                r"Money\s+market\s+rates|Domestic\s+financial\s+markets|Policy\s+repo\s+rate|Repo\s+rate|"
                r"Indian\s+economy|Economic\s+activity|Consumption\s+expenditure|Export\s+demand|Fixed\s+investment|"
                r"BSE\s+Sensex|Nifty\s+50|BSE\s+MidCap|BSE\s+SmallCap|FPIs|FIIs|RBI|Reserve\s+Bank\s+of\s+India|US\s+Fed|Bank\s+of\s+Japan|India|GDP)\b",
                sentence,
                re.IGNORECASE,
            )
            if m_subj:
                matched_subj = m_subj.group(1).strip()
                sentence_entity = re.sub(r"\s*[-–—]\s*", " - ", matched_subj)

            # Sentence-specific fiscal period / year
            sent_fy = fiscal_year
            m_sent_fy = re.search(r"\b(20\d\d-\d\d|FY\s*\d\d|FY\s*20\d\d|H[12]:20\d\d-\d\d|Q[1-4]:20\d\d-\d\d)\b", sentence, re.IGNORECASE)
            if m_sent_fy:
                raw_fy = m_sent_fy.group(1).replace(" ", "").upper()
                sent_fy = f"FY{raw_fy}" if not raw_fy.startswith("FY") and ":" not in raw_fy else raw_fy

            # 1. Macro / Economic Growth, Decline, and Comparisons
            macro_patterns = [
                (r"(?:is\s+estimated\s+to\s+have\s+grown|estimated\s+to\s+grow|grown|grew|growing|increased|increasing|rose|rising|expanded|expanding|surged|accelerated)\s+by\s+([\d,.]+\s*(?:per\s+cent|percent|%|bps|basis\s+points))", "Growth Rate", "macroeconomic"),
                (r"(?:declined|declining|fell|falling|dropped|dropping|decreased|decreasing|contracted|contracting|slowed|moderated)\s+(?:by|to)\s+([\d,.]+\s*(?:per\s+cent|percent|%|bps|basis\s+points))", "Decline Rate", "macroeconomic"),
                (r"(?:as\s+compared\s+with|compared\s+(?:with|to)|against|up\s+from|down\s+from)\s+([\d,.]+\s*(?:per\s+cent|percent|%|bps)(?:\s+a\s+year\s+ago|\s+in\s+the\s+previous\s+year|\s+prior\s+year)?)", "Baseline Comparison", "macroeconomic"),
                (r"(?:touching\s+a\s+new\s+high\s+of|high\s+of|breach\s+the|crossing\s+the|peaked\s+at)\s+([\d,]+(?:\.\d+)?)", "Index Milestone", "macroeconomic"),
                (r"net\s+sales\s+of\s+([$€£₹]?\s*[\d,.]+\s*(?:crore|lakh|billion|million|cr)?)", "Net Sales", "financial"),
                (r"net\s+purchases\s+of\s+([$€£₹]?\s*[\d,.]+\s*(?:crore|lakh|billion|million|cr)?)", "Net Purchases", "financial"),
                (r"(?:repo\s+rate|reverse\s+repo\s+rate|crr|slr|policy\s+rate)\s+(?:was|stood\s+at|is|remained|at)\s+([\d,.]+\s*(?:per\s+cent|percent|%|bps))", "Policy Rate", "macroeconomic"),
                (r"(?:fiscal\s+deficit|revenue\s+deficit|cad|current\s+account\s+deficit)\s+(?:stood\s+at|was|is|at)\s+([\d,.]+\s*(?:per\s+cent|percent|%|bps)(?:\s+of\s+gdp)?)", "Deficit Ratio", "macroeconomic"),
            ]
            for regex, pred_name, cat in macro_patterns:
                match = re.search(regex, sentence, re.IGNORECASE)
                if match:
                    val_text = match.group(1).strip()
                    num_val = self._parse_numeric(val_text)
                    unit = "%" if ("%" in val_text or "per cent" in val_text or "percent" in val_text) else currency

                    facts.append(
                        ExtractedFact(
                            subject=sentence_entity,
                            predicate=pred_name,
                            object_value=val_text,
                            object_numeric=num_val,
                            unit=unit,
                            original_text=sentence,
                            evidence_excerpt=sentence,
                            category=cat,
                            fiscal_year=sent_fy,
                            scope=scope,
                            basis=basis,
                            currency=currency,
                            confidence=0.95,
                        )
                    )

            # 2. Qualitative Trend & Policy Signals
            trend_patterns = [
                (r"(headline\s+inflation|food\s+inflation|core\s+inflation|core\s+disinflation)\s+(moderated\s+further|softened|remained\s+volatile\s+and\s+elevated|remained\s+elevated|decelerated|accelerated)", "Inflation Trend", "macroeconomic"),
                (r"(?:pursued|pursuing|achieved)\s+(fiscal\s+consolidation)", "Fiscal Policy", "governance"),
                (r"(tax\s+receipts|capital\s+expenditure|credit\s+growth|deposit\s+growth)\s+(remained\s+robust|recorded\s+modest\s+growth|accelerated|slowed)", "Financial Trend", "financial"),
                (r"(issuances?\s+of\s+certificates\s+of\s+deposit(?:\s+\(cds\))?|money\s+market\s+rates)\s+(increased|remained\s+range[- ]bound|broadly\s+evolved\s+in\s+an\s+orderly\s+manner)", "Market Dynamic", "financial"),
                (r"(indian\s+economy|economic\s+activity)\s+(exhibited\s+resilience|recovered\s+in\s+[A-Za-z0-9:\-]+|rebounded)", "Economic Status", "macroeconomic"),
                (r"(consumption\s+expenditure\s+and\s+export\s+demand|consumption\s+expenditure|export\s+demand)\s+(accelerated)", "Demand Trend", "macroeconomic"),
                (r"(fixed\s+investment)\s+(recorded\s+a\s+moderation|moderated)", "Investment Trend", "macroeconomic"),
            ]
            for regex, pred_name, cat in trend_patterns:
                match = re.search(regex, sentence, re.IGNORECASE)
                if match:
                    subj = match.group(1).title() if len(match.groups()) >= 2 else sentence_entity
                    val_text = match.group(2) if len(match.groups()) >= 2 else match.group(1)
                    facts.append(
                        ExtractedFact(
                            subject=subj,
                            predicate=pred_name,
                            object_value=val_text,
                            object_numeric=None,
                            unit=None,
                            original_text=sentence,
                            evidence_excerpt=sentence,
                            category=cat,
                            fiscal_year=sent_fy,
                            scope=scope,
                            basis=basis,
                            currency=currency,
                            confidence=0.92,
                        )
                    )

            # 2. Corporate Financial metrics
            metric_patterns = [
                (r"(revenue|total revenue|sales)\s+(?:was|were|of|reached|is|totaled)\s+([$€£₹]?\s*[\d,.]+\s*(?:billion|million|trillion|crore|lakh|B|M|k)?)", "Revenue", "financial"),
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
                            subject=sentence_entity,
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

            # 3. Executive / Governance
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
                            subject=sentence_entity,
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
        """Parse numeric values including billion/million/crore multipliers and (parentheses) negative notation."""
        if not val_str:
            return None
        cleaned = str(val_str).strip()
        is_negative = False
        if cleaned.startswith("(") and cleaned.endswith(")"):
            is_negative = True
            cleaned = cleaned[1:-1].strip()

        cleaned = cleaned.replace("$", "").replace("€", "").replace("£", "").replace("₹", "").replace(",", "").replace("%", "").strip()
        multiplier = 1.0
        if re.search(r"trillion|T\b", cleaned, re.IGNORECASE):
            multiplier = 1_000_000_000_000.0
            cleaned = re.sub(r"trillion|T\b", "", cleaned, flags=re.IGNORECASE).strip()
        elif re.search(r"billion|B\b", cleaned, re.IGNORECASE):
            multiplier = 1_000_000_000.0
            cleaned = re.sub(r"billion|B\b", "", cleaned, flags=re.IGNORECASE).strip()
        elif re.search(r"crore\b", cleaned, re.IGNORECASE):
            multiplier = 10_000_000.0
            cleaned = re.sub(r"crore\b", "", cleaned, flags=re.IGNORECASE).strip()
        elif re.search(r"lakh\b", cleaned, re.IGNORECASE):
            multiplier = 100_000.0
            cleaned = re.sub(r"lakh\b", "", cleaned, flags=re.IGNORECASE).strip()
        elif re.search(r"million|M\b", cleaned, re.IGNORECASE):
            multiplier = 1_000_000.0
            cleaned = re.sub(r"million|M\b", "", cleaned, flags=re.IGNORECASE).strip()
        elif re.search(r"thousand|k\b", cleaned, re.IGNORECASE):
            multiplier = 1_000.0
            cleaned = re.sub(r"thousand|k\b", "", cleaned, flags=re.IGNORECASE).strip()

        match = re.search(r"[-+]?\d*\.?\d+", cleaned)
        if match:
            try:
                val = float(match.group()) * multiplier
                return -abs(val) if is_negative else val
            except ValueError:
                return None
        return None
