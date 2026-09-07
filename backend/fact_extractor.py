"""Fact Extractor using Google Gemini with Exhaustive Directive Prompting, Two-Pass Extraction, Fact-Type Reasoning, and Table Coverage Validation."""

from __future__ import annotations
import os
import json
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv

from backend.table_cleaner import strip_table_artifacts, clean_table_headers
from backend.pdf_parser import extract_page_chunks_with_bbox, group_chunks_into_blocks

try:
    from google import genai
except ImportError:
    genai = None

load_dotenv()

logger = logging.getLogger(__name__)

# ============================================================
# FIX 3: fact_type_reasoning (backend/fact_extractor.py)
# ============================================================
#
# PROBLEM: fact_type is being assigned without justification, so the model
# pattern-matches on table position/row label instead of actually reading
# what the fact says (a legal/regulatory citation was tagged "Organization").
#
# FIX: force a one-line reasoning field BEFORE the type label in the JSON
# schema. Making the model commit to *why* before *what* measurably
# improves classification because it can't skip straight to a lazy guess.

EXTRACTION_PROMPT_TEMPLATE = """
You are extracting factual claims from a document for a fact-checking system.

Given the following text (from page {page_number}), extract every distinct
factual claim -- numerical or semantic. Do not invent facts not present in
the text. Err on the side of extracting too much rather than too little.

If the text contains placeholder column labels like "[unlabeled column —
infer from context]", use the surrounding row/column context to understand
what that value represents -- do NOT include the placeholder text itself
in your output.

Do NOT extract section headings, table captions, or document boilerplate
(QR codes, disclaimers, page footers) as facts -- only extract substantive
claims with actual values or assertions.

For each fact, output a JSON object with these fields, IN THIS ORDER:
- "source_quote": the exact verbatim sentence(s) from the text supporting this fact
- "fact_text": a clear, self-contained restatement of the fact (never include
   placeholder labels like "Column_N" or "Unnamed" in this text)
- "fact_type_reasoning": one sentence explaining WHY this fact belongs to the
   category you are about to assign -- base this on the fact's actual content,
   not its position in a table or document section
- "fact_type": your best inferred category, consistent with your reasoning above
   (e.g. "financial", "regulatory", "personnel", "date", "location", "legal" —
   or invent a new category if none fit)
- "value": the numeric value if applicable, else null
- "unit": the unit if applicable (e.g. "INR crore", "%", "years"), else null
- "time_period": any date, fiscal year, or period this fact is scoped to, else null
- "page_number": {page_number}

Return ONLY a JSON array of these objects. No preamble, no markdown formatting.

TEXT:
\"\"\"
{chunk_text}
\"\"\"
"""

# ── PASS 1: Directive Exhaustive Prompt ──────────────────────────────────────────
EXTRACTION_PROMPT_PASS1 = """You are a precision fact extraction engine for financial, enterprise, and corporate documents.
Extract EVERY factual claim from this text/table — do not skip anything, even minor line items. Include:
- Every numeric figure with its label, unit, and time period
- Every named entity claim (people, roles, dates of appointment/resignation, subsidiaries)
- Every explicit relationship stated (e.g. "X is a subsidiary of Y", "Company A acquired Company B")
- Footnote disclosures, accounting basis (GAAP vs Non-GAAP), and period definitions

CRITICAL INSTRUCTIONS:
- Err on the side of extracting too much rather than too little — a downstream system will filter noise later.
- If the text contains placeholder labels like "[unlabeled column — infer from context]", use surrounding context to infer meaning — never output "Column_N" or "Unnamed".
- Do NOT extract section headings, table captions, or document boilerplate (QR codes, disclaimers, page footers, watermarks) as facts — only extract substantive claims with actual values, entities, metrics, or assertions.

For tables: extract EVERY row, not just totals — sub-line-items matter!
For each row and column intersection:
- Create a distinct atomic fact combining the row metric + column header (e.g. "Total equity as at December 31, 2021 was ₹59,798.47 million")
- Extract exact numeric values (resolving currency symbols like ₹/$, millions/billions/crore, parentheses for negative numbers)
- Identify the correct unit ("INR million", "INR", "USD", "%", "employees", etc.) and time period (e.g. "December 31, 2021", "FY2022", "FY2023", "Q3 2024")
- Use the table row or cell context as `source_quote`

For each fact, output a JSON object with these fields, IN THIS EXACT ORDER:
- "source_quote": the exact verbatim sentence or table row from the text supporting this fact
- "fact_text": a clear, self-contained restatement of the fact (never include placeholder labels like "Column_N" or "Unnamed")
- "fact_type_reasoning": one sentence explaining WHY this fact belongs to the category you are assigning based on its substantive content
- "fact_type": inferred category ("financial", "regulatory", "personnel", "governance", "operational", "relationship", "legal")
- "value": the numeric value if applicable (float), else null
- "unit": the unit if applicable (e.g. "INR million", "INR", "USD", "%", "employees"), else null
- "time_period": date, fiscal year, or quarter this fact is scoped to (e.g. "December 31, 2021", "FY2023"), else null
- "page_number": {page_number}

Return ONLY a JSON array of these objects. No preamble, no markdown formatting.

DOCUMENT TEXT (Page {page_number}):
\"\"\"
{chunk_text}
\"\"\"
"""

# ── PASS 2: Targeted Missed-Fact Recovery Prompt ────────────────────────────────
EXTRACTION_PROMPT_PASS2 = """You are a precision fact extraction QA auditor.
Here is the original text from page {page_number} and the initial list of extracted facts.

What facts, especially numeric figures, sub-line items, table rows, footnote details, percentage changes, or explicit entity relationships, might have been missed in this list?

Examine carefully:
1. Every individual sub-line item in tables (ensure no rows or columns were skipped).
2. Every footnote disclosure at the bottom of tables or pages.
3. Specific dates, role titles, and operational metrics mentioned in narrative text.

Pass 1 Extracted Facts:
{pass1_summary}

Original Document Text (Page {page_number}):
\"\"\"
{chunk_text}
\"\"\"

Output ONLY a JSON array of any ADDITIONAL or MISSED facts with fields:
[
  {{
    "source_quote": "...",
    "fact_text": "...",
    "fact_type_reasoning": "one sentence explaining why this fact belongs to the category",
    "fact_type": "financial" | "regulatory" | "personnel" | "governance" | "operational" | "relationship" | "legal",
    "value": float or null,
    "unit": str or null,
    "time_period": str or null,
    "page_number": {page_number}
  }}
]
If no facts were missed, return an empty array: []
"""


def extract_facts_from_block(client: Any, block: dict, model: str = "gemini-2.0-flash") -> List[Dict[str, Any]]:
    """
    block: one item from group_chunks_into_blocks(), containing
           {"text", "bbox", "page_number"}

    Returns a list of fact dicts, each still carrying the ORIGINAL bbox
    from the block it came from -- so evidence highlighting always points
    at the exact text the LLM actually read, with zero re-searching.
    """
    cleaned_text = strip_table_artifacts(block["text"])

    prompt = EXTRACTION_PROMPT_TEMPLATE.format(
        page_number=block["page_number"],
        chunk_text=cleaned_text,
    )

    if client is None:
        # Run deterministic extractor if client is not provided
        extractor = FactExtractor()
        facts = extractor.extract_facts(cleaned_text, page_number=block["page_number"])
        for f in facts:
            f["bbox"] = block.get("bbox")
        return facts

    raw = ""
    try:
        # Check if google-genai Client
        if hasattr(client, "models") and hasattr(client.models, "generate_content"):
            response = client.models.generate_content(model=model, contents=prompt)
            raw = response.text.strip()
        elif hasattr(client, "generate_content"):
            response = client.generate_content(prompt)
            raw = response.text.strip()
    except Exception as e:
        logger.warning(f"Error calling LLM for block on page {block['page_number']}: {e}")
        extractor = FactExtractor()
        facts = extractor.extract_facts(cleaned_text, page_number=block["page_number"])
        for f in facts:
            f["bbox"] = block.get("bbox")
        return facts

    raw = re.sub(r"^```json\s*|\s*```$", "", raw)  # strip markdown fences if present
    start_idx = raw.find("[")
    end_idx = raw.rfind("]")
    if start_idx != -1 and end_idx != -1:
        raw = raw[start_idx:end_idx + 1]

    try:
        facts = json.loads(raw)
        if isinstance(facts, dict):
            facts = [facts]
    except json.JSONDecodeError:
        print(f"[WARN] Failed to parse JSON for page {block['page_number']}: {raw[:200]}")
        extractor = FactExtractor()
        facts = extractor.extract_facts(cleaned_text, page_number=block["page_number"])
        for f in facts:
            f["bbox"] = block.get("bbox")
        return facts

    valid_facts = []
    for fact in facts:
        fact["bbox"] = block.get("bbox")          # <-- carried straight through, never re-searched
        fact["page_number"] = block["page_number"]
        # defensive second pass in case any artifact slipped through the model itself
        fact["fact_text"] = strip_table_artifacts(fact.get("fact_text", ""))
        if not fact.get("fact_type_reasoning"):
            fact["fact_type_reasoning"] = f"Classified as {fact.get('fact_type', 'general')} based on substantive content."
        valid_facts.append(fact)

    return valid_facts


def process_page(pdf_path: str, page_num: int, client: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Process a single page of a PDF and extract facts with bboxes intact."""
    line_chunks = extract_page_chunks_with_bbox(pdf_path, page_num)
    blocks = group_chunks_into_blocks(line_chunks)

    all_facts = []
    for block in blocks:
        if len(block["text"].strip()) < 15:
            continue  # skip near-empty fragments (stray page numbers, etc.)
        facts = extract_facts_from_block(client, block)
        all_facts.extend(facts)

    return all_facts


class FactExtractor:
    """Extract structured facts from text chunks using two-pass Gemini LLM extraction, fact-type reasoning, and structural table verification."""

    def __init__(self, api_key: Optional[str] = None, enable_two_pass: bool = True):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.enable_two_pass = enable_two_pass
        self.client = None
        self._init_client()

    def _init_client(self):
        if not self.api_key:
            logger.info("No Gemini API key found. Using deterministic extraction fallback.")
            return

        # Attempt 1: google-genai SDK (recommended)
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            self.sdk_type = "google-genai"
            return
        except Exception:
            pass

        # Attempt 2: google.generativeai
        try:
            import google.generativeai as genai_legacy
            genai_legacy.configure(api_key=self.api_key)
            model_name = os.getenv("EXTRACTION_MODEL", "gemini-flash-latest")
            self.legacy_model = genai_legacy.GenerativeModel(model_name)
            self.sdk_type = "google.generativeai"
            return
        except Exception:
            pass

        self.client = None

    def extract_facts(self, chunk_text: str, page_number: int, bbox: Optional[Tuple[float, float, float, float]] = None) -> List[Dict[str, Any]]:
        """
        Extract factual claims from a single chunk using:
        1. Artifact cleaning (stripping Column_N and Unnamed: N)
        2. Pass 1: Directive exhaustive LLM extraction with fact_type_reasoning
        3. Pass 2: Targeted missed-fact QA recovery pass
        4. Table coverage validation & deterministic cell backfill
        5. High-precision deduplication
        """
        if not chunk_text or not chunk_text.strip():
            return []

        # Strip table placeholders from chunk text
        cleaned_chunk_text = strip_table_artifacts(chunk_text)

        # Safe ascii preview for Windows cp1252 console logging
        preview = cleaned_chunk_text[:140].replace('\n', ' ')
        safe_preview = preview.encode('ascii', 'backslashreplace').decode('ascii')
        logger.info(f"[FactExtraction] Processing Page {page_number} (Length: {len(cleaned_chunk_text)} chars) -> Preview: {safe_preview}")
        try:
            print(f"[FactExtraction] Page {page_number} ({len(cleaned_chunk_text)} chars): {safe_preview}")
        except Exception:
            pass

        all_facts: List[Dict[str, Any]] = []

        # ── LLM Extraction Path ───────────────────────────────────────
        if self.client or hasattr(self, "legacy_model"):
            try:
                # --- PASS 1: Broad / Exhaustive Extraction ---
                prompt_pass1 = EXTRACTION_PROMPT_PASS1.format(
                    page_number=page_number,
                    chunk_text=cleaned_chunk_text,
                )
                raw_p1 = self._call_gemini(prompt_pass1)
                pass1_facts = self._parse_json_response(raw_p1, page_number)
                all_facts.extend(pass1_facts)

                # --- PASS 2: Targeted Missed-Fact Recovery ---
                if self.enable_two_pass and pass1_facts:
                    pass1_summary = "\n".join(f"- {f['fact_text']}" for f in pass1_facts[:25])
                    prompt_pass2 = EXTRACTION_PROMPT_PASS2.format(
                        page_number=page_number,
                        pass1_summary=pass1_summary,
                        chunk_text=cleaned_chunk_text,
                    )
                    try:
                        raw_p2 = self._call_gemini(prompt_pass2)
                        pass2_facts = self._parse_json_response(raw_p2, page_number)
                        all_facts.extend(pass2_facts)
                    except Exception as e:
                        logger.debug(f"Pass 2 extraction skipped: {e}")

            except Exception as e:
                logger.warning(f"LLM fact extraction failed: {e}. Falling back to deterministic.")

        # ── Table Structural Coverage Verification & Backfill ─────────
        # Check if chunk contains Markdown tables and ensure full cell coverage
        table_facts = self._validate_and_backfill_tables(all_facts, cleaned_chunk_text, page_number)
        all_facts.extend(table_facts)

        # If LLM didn't run or returned nothing, run deterministic narrative extractor
        if not all_facts:
            all_facts = self._extract_deterministic(cleaned_chunk_text, page_number)

        # Deduplicate facts
        deduped = self._deduplicate_facts(all_facts)

        # Attach bbox and sanitize fact_text
        for f in deduped:
            if bbox is not None and "bbox" not in f:
                f["bbox"] = bbox
            f["fact_text"] = strip_table_artifacts(f.get("fact_text", ""))
            if not f.get("fact_type_reasoning"):
                f["fact_type_reasoning"] = f"Classified as {f.get('fact_type', 'general')} based on content context."

        return deduped

    def _call_gemini(self, prompt: str) -> str:
        models_to_try = [
            os.getenv("EXTRACTION_MODEL", "gemini-flash-latest"),
            "gemini-2.5-flash",
            "gemini-flash-latest",
            "gemini-2.0-flash",
        ]
        unique_models = []
        for m in models_to_try:
            if m and m not in unique_models:
                unique_models.append(m)

        last_err = None
        if hasattr(self, "sdk_type") and self.sdk_type == "google-genai" and self.client:
            for model_name in unique_models:
                try:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                    )
                    return response.text
                except Exception as e:
                    last_err = e
                    continue
        elif hasattr(self, "legacy_model"):
            try:
                response = self.legacy_model.generate_content(prompt)
                return response.text
            except Exception as e:
                last_err = e

        if last_err:
            raise last_err
        raise RuntimeError("No LLM client configured")

    def _parse_json_response(self, text: str, page_number: int) -> List[Dict[str, Any]]:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        start_idx = text.find("[")
        end_idx = text.rfind("]")
        if start_idx != -1 and end_idx != -1:
            text = text[start_idx:end_idx + 1]

        data = json.loads(text)
        if isinstance(data, dict):
            data = [data]

        valid_facts = []
        for item in data:
            if isinstance(item, dict) and item.get("fact_text"):
                val = item.get("value")
                if val is not None:
                    try:
                        val = self._parse_numeric(str(val))
                    except (ValueError, TypeError):
                        val = None

                time_period = item.get("time_period")
                if not time_period and item.get("fact_text"):
                    date_match = re.search(r"(?:as at|as of|for the (?:year|period) ended\s+)?((?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},\s+\d{4})", item["fact_text"], re.I)
                    if date_match:
                        time_period = date_match.group(1).strip()
                    elif re.search(r"(?:FY\s*\d\d\d\d|FY\s*\d\d|Q[1-4]|20\d\d)", item["fact_text"], re.I):
                        pmatch = re.search(r"(?:FY\s*\d\d\d\d|FY\s*\d\d|Q[1-4]|20\d\d)", item["fact_text"], re.I)
                        time_period = pmatch.group(0).strip()

                reasoning = item.get("fact_type_reasoning") or f"Classified as {item.get('fact_type', 'general')} based on substantive content."
                valid_facts.append({
                    "fact_text": strip_table_artifacts(str(item["fact_text"])).strip(),
                    "fact_type_reasoning": str(reasoning).strip(),
                    "fact_type": str(item.get("fact_type", "general")).strip(),
                    "value": val,
                    "unit": item.get("unit"),
                    "time_period": time_period,
                    "source_quote": str(item.get("source_quote", item["fact_text"])).strip(),
                    "page_number": item.get("page_number", page_number),
                })
        return valid_facts

    def _validate_and_backfill_tables(
        self,
        current_facts: List[Dict[str, Any]],
        chunk_text: str,
        page_number: int,
    ) -> List[Dict[str, Any]]:
        """Validate whether all numbers and line items in Markdown tables within chunk_text are accounted for."""
        backfilled_facts = []
        table_lines = []
        in_table = False
        all_tables_lines = []

        for line in chunk_text.split("\n"):
            line_s = line.strip()
            if line_s.startswith("|") and line_s.endswith("|"):
                table_lines.append(line_s)
                in_table = True
            else:
                if in_table and len(table_lines) >= 2:
                    all_tables_lines.append(table_lines)
                    table_lines = []
                in_table = False
        if in_table and len(table_lines) >= 2:
            all_tables_lines.append(table_lines)

        for t_lines in all_tables_lines:
            deterministic_facts = self._parse_markdown_table_deterministic(t_lines, page_number, context_text=chunk_text)
            if not deterministic_facts:
                continue

            existing_signatures = set()
            for f in current_facts:
                text_clean = re.sub(r"\s+", " ", f.get("fact_text", "")).strip().lower()
                val = f.get("value")
                existing_signatures.add(text_clean)
                if val is not None:
                    existing_signatures.add((text_clean, val))

            for df in deterministic_facts:
                df_text_clean = re.sub(r"\s+", " ", df.get("fact_text", "")).strip().lower()
                df_val = df.get("value")
                df_period = str(df.get("time_period", "")).lower()

                already_covered = False
                if df_text_clean in existing_signatures:
                    already_covered = True
                elif df_val is not None and (df_text_clean, df_val) in existing_signatures:
                    already_covered = True
                else:
                    for f in current_facts:
                        f_text_l = f.get("fact_text", "").lower()
                        f_period = str(f.get("time_period", "")).lower()
                        if df_val is not None and f.get("value") == df_val:
                            # Verify both significant tokens and time period match
                            df_words = [w for w in re.findall(r"\b[a-zA-Z]{3,}\b", df_text_clean) if w not in {"total", "was", "for", "the", "and", "inr", "usd", "million", "crore"}]
                            if df_words and all(w in f_text_l for w in df_words):
                                if not df_period or not f_period or df_period == f_period or df_period in f_text_l:
                                    already_covered = True
                                    break

                if not already_covered:
                    backfilled_facts.append(df)

        return backfilled_facts

    def _deduplicate_facts(self, facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate facts based on normalized semantic signature."""
        seen = set()
        unique = []
        for f in facts:
            text_norm = re.sub(r"\s+", " ", f.get("fact_text", "")).strip().lower()
            val = f.get("value")
            period = str(f.get("time_period", "")).lower()
            page = f.get("page_number", 1)

            sig = (text_norm, val, period, page)
            if sig not in seen and text_norm:
                seen.add(sig)
                unique.append(f)
        return unique

    def _parse_numeric(self, val_str: str) -> Optional[float]:
        """Convert number strings with currency, parentheses, and multipliers into float."""
        if not val_str:
            return None
        cleaned = str(val_str).replace("$", "").replace("€", "").replace("£", "").replace("₹", "").replace(",", "").replace("%", "").strip()
        is_negative = False
        if cleaned.startswith("(") and cleaned.endswith(")"):
            is_negative = True
            cleaned = cleaned[1:-1].strip()
        elif cleaned.startswith("-"):
            is_negative = True
            cleaned = cleaned[1:].strip()

        multiplier = 1.0
        if re.search(r"crore|cr\b", cleaned, re.IGNORECASE):
            multiplier = 10_000_000.0
            cleaned = re.sub(r"crore|cr\b", "", cleaned, flags=re.IGNORECASE).strip()
        elif re.search(r"lakh|lac\b", cleaned, re.IGNORECASE):
            multiplier = 100_000.0
            cleaned = re.sub(r"lakh|lac\b", "", cleaned, flags=re.IGNORECASE).strip()
        elif re.search(r"billion|B\b", cleaned, re.IGNORECASE):
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

    def _parse_markdown_table_deterministic(self, table_lines: List[str], page_number: int, context_text: str = "") -> List[Dict[str, Any]]:
        """Parse rows and columns of a markdown table directly into atomic facts."""
        facts = []
        cleaned_lines = [l.strip() for l in table_lines if l.strip().startswith("|") and l.strip().endswith("|")]
        if len(cleaned_lines) < 2:
            return facts

        # Identify header line and data lines (skipping --- separator rows)
        header_line = None
        data_rows = []
        for line_s in cleaned_lines:
            cells = [c.strip() for c in line_s.split("|")[1:-1]]
            if not cells:
                continue
            if all(re.match(r"^:?-+:?$", c) for c in cells if c):
                continue
            if header_line is None:
                header_line = line_s
            else:
                data_rows.append(line_s)

        if not header_line or not data_rows:
            return facts

        raw_headers = [c.strip() for c in header_line.split("|")[1:-1]]
        headers = clean_table_headers(raw_headers)
        if not headers:
            return facts

        # Infer context-wide unit and currency
        inherited_unit = None
        combined_context = (context_text + "\n" + "\n".join(table_lines)).lower()
        if "in ₹ million" in combined_context or "rs. in million" in combined_context or "in rs million" in combined_context or "in inr million" in combined_context:
            inherited_unit = "INR million"
        elif "in ₹ crore" in combined_context or "rs. in crore" in combined_context or "in rs crore" in combined_context:
            inherited_unit = "INR crore"
        elif "in $ million" in combined_context or "usd million" in combined_context:
            inherited_unit = "USD million"
        elif "in million" in combined_context:
            inherited_unit = "million"

        for row_str in data_rows:
            cells = [strip_table_artifacts(c.strip()) for c in row_str.split("|")[1:-1]]
            if not cells or not any(cells):
                continue

            row_label = cells[0]
            if not row_label or len(row_label) < 2 or row_label.startswith("---") or "[unlabeled" in row_label.lower():
                continue

            for col_idx, val_str in enumerate(cells[1:], 1):
                if not val_str or val_str in {"-", "—", "N/A", "NA", "nil", "Nil", "[unlabeled column — infer from context]"}:
                    continue

                col_header = headers[col_idx] if col_idx < len(headers) else ""
                num_val = self._parse_numeric(val_str)
                unit = inherited_unit
                if not unit:
                    if "%" in val_str:
                        unit = "%"
                    elif "$" in val_str:
                        unit = "USD"
                    elif "₹" in val_str or "Rs" in val_str:
                        unit = "INR"

                period = None
                date_match = re.search(r"(?:as at|as of|for the (?:year|period) ended\s+)?((?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},\s+\d{4})", col_header, re.I)
                if date_match:
                    period = date_match.group(1).strip()
                elif re.search(r"(?:FY\s*\d\d\d\d|FY\s*\d\d|Q[1-4]|20\d\d)", col_header, re.I):
                    period = re.sub(r"FY\s+(\d+)", r"FY\1", col_header.strip(), flags=re.I)

                if period:
                    if period.upper().startswith("FY") or "FY" in period.upper():
                        fact_statement = f"{row_label} for {period} was {val_str}."
                    else:
                        fact_statement = f"{row_label} as at {period} was {val_str}."
                elif col_header and "[unlabeled" not in col_header.lower():
                    fact_statement = f"{row_label} for {col_header} was {val_str}."
                else:
                    fact_statement = f"{row_label} was {val_str}."

                if inherited_unit and "million" in inherited_unit.lower() and "million" not in fact_statement.lower():
                    fact_statement = fact_statement[:-1] + f" ({inherited_unit})."

                fact_type = "financial" if (num_val is not None or inherited_unit or "$" in val_str or "₹" in val_str) else "operational"
                facts.append({
                    "fact_text": strip_table_artifacts(fact_statement),
                    "fact_type_reasoning": f"Extracted from structured table row '{row_label}' with column header '{col_header}'.",
                    "fact_type": fact_type,
                    "value": num_val,
                    "unit": unit,
                    "time_period": period,
                    "source_quote": row_str.strip(),
                    "page_number": page_number,
                })

        return facts

    def _extract_deterministic(self, chunk_text: str, page_number: int) -> List[Dict[str, Any]]:
        """Deterministic rule-based extractor for narrative text and structured Markdown tables."""
        facts = []
        lines = chunk_text.split("\n")

        # 1. First parse structured Markdown tables in chunk
        table_lines = []
        in_table = False
        for line in lines:
            line_s = line.strip()
            if line_s.startswith("|") and line_s.endswith("|"):
                table_lines.append(line_s)
                in_table = True
            else:
                if in_table and len(table_lines) >= 2:
                    facts.extend(self._parse_markdown_table_deterministic(table_lines, page_number, context_text=chunk_text))
                    table_lines = []
                in_table = False
        if in_table and len(table_lines) >= 2:
            facts.extend(self._parse_markdown_table_deterministic(table_lines, page_number, context_text=chunk_text))

        # 2. Parse narrative lines
        for line in lines:
            line_clean = line.strip()
            if not line_clean or len(line_clean) < 8 or line_clean.startswith("|"):
                continue

            # Executive / Personnel facts (CEO, CFO, Headcount)
            ceo_match = re.search(r"(?:Chief Executive Officer|CEO)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", line_clean, re.I)
            if ceo_match:
                name = ceo_match.group(1).strip()
                facts.append({
                    "fact_text": f"Chief Executive Officer is {name}.",
                    "fact_type_reasoning": "Personnel leadership assertion identifying the Chief Executive Officer.",
                    "fact_type": "personnel",
                    "value": None,
                    "unit": None,
                    "time_period": "2023" if "2023" in chunk_text else ("2024" if "2024" in chunk_text else None),
                    "source_quote": line_clean,
                    "page_number": page_number,
                })

            headcount_match = re.search(r"(\d[\d,]*)\s+(?:full-time employees|team members|employees)", line_clean, re.I)
            if headcount_match:
                count_str = headcount_match.group(1).replace(",", "")
                try:
                    val = float(count_str)
                    facts.append({
                        "fact_text": f"Employee headcount is {int(val)} employees.",
                        "fact_type_reasoning": "Operational headcount metric quantifying total workforce size.",
                        "fact_type": "personnel",
                        "value": val,
                        "unit": "employees",
                        "time_period": "2023" if "2023" in chunk_text else ("2024" if "2024" in chunk_text else None),
                        "source_quote": line_clean,
                        "page_number": page_number,
                    })
                except ValueError:
                    pass

            # Revenue metrics
            rev_match = re.search(r"(?:total(?:\s+full-year)?\s+revenue|annual revenue|revenue)(?:\s+(?:of|was|reached|is))?[:\s]+\$?([0-9,]+(?:\.[0-9]+)?)\s*(million|billion|crore|lakh|M|B|k)?", line_clean, re.I)
            if rev_match:
                raw_num = rev_match.group(1).replace(",", "")
                multiplier = rev_match.group(2)
                try:
                    num = float(raw_num)
                    if multiplier:
                        m_lower = multiplier.lower()
                        if "b" in m_lower or "billion" in m_lower:
                            num *= 1_000_000_000
                        elif "m" in m_lower or "million" in m_lower:
                            num *= 1_000_000
                        elif "crore" in m_lower:
                            num *= 10_000_000
                        elif "lakh" in m_lower:
                            num *= 100_000
                    facts.append({
                        "fact_text": f"Total Revenue is ${num:,.0f}.",
                        "fact_type_reasoning": "Financial performance metric quantifying top-line company revenue.",
                        "fact_type": "financial",
                        "value": num,
                        "unit": "USD",
                        "time_period": "FY2023" if "2023" in chunk_text else ("FY2024" if "2024" in chunk_text else None),
                        "source_quote": line_clean,
                        "page_number": page_number,
                    })
                except ValueError:
                    pass

            # Net Income
            income_match = re.search(r"(?:GAAP\s+)?Net\s+Income[:\s]+\$?([0-9,]+(?:\.[0-9]+)?)\s*(million|billion|M|B)?", line_clean, re.I)
            if income_match:
                raw_num = income_match.group(1).replace(",", "")
                multiplier = income_match.group(2)
                try:
                    num = float(raw_num)
                    if multiplier:
                        m_lower = multiplier.lower()
                        if "b" in m_lower or "billion" in m_lower:
                            num *= 1_000_000_000
                        elif "m" in m_lower or "million" in m_lower:
                            num *= 1_000_000
                    facts.append({
                        "fact_text": f"Net Income is ${num:,.0f}.",
                        "fact_type_reasoning": "Financial profitability metric quantifying bottom-line net income.",
                        "fact_type": "financial",
                        "value": num,
                        "unit": "USD",
                        "time_period": "FY2023" if "2023" in chunk_text else ("FY2024" if "2024" in chunk_text else None),
                        "source_quote": line_clean,
                        "page_number": page_number,
                    })
                except ValueError:
                    pass

        return facts
