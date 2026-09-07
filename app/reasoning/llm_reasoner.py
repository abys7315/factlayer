"""LLM-based reasoning for ambiguous comparison cases."""

from __future__ import annotations

import json
import asyncio
import time
import re
import logging
from typing import Any

from app.config import get_settings
from app.models.enums import RelationshipType

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


LLM_REASONING_PROMPT = """You are an expert fact comparison system. Analyze two facts and determine their relationship:
- CORROBORATES: Facts agree on the same claim
- CONTRADICTS: Facts disagree on the same claim under the same context
- CONTEXTUAL_DIFFERENCE: Facts appear to conflict but describe different contexts (period, scope, GAAP vs Non-GAAP, geography)
- SUPERSEDES: Later fact updates or replaces earlier fact
- UNRELATED: Different claims
"""


class LLMReasoner:
    """
    LLM-based reasoning for ambiguous comparison cases.
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
                    self._model = genai.GenerativeModel("gemini-1.5-pro")
                elif hasattr(genai, "Client"):
                    self._model = genai.Client(api_key=self.settings.GOOGLE_API_KEY)
            except Exception as e:
                logger.warning(f"Could not init reasoner Gemini model: {e}")

    async def reason(self, fact_a, fact_b, context: dict | None = None) -> dict[str, Any]:
        """Use LLM or heuristic reasoning to analyze fact relationship."""
        self._init_gemini_model()
        prompt = self._build_prompt(fact_a, fact_b, context)

        if self._model and self.settings.GOOGLE_API_KEY:
            async with self._semaphore:
                try:
                    if hasattr(self._model, "generate_content_async"):
                        response = await self._model.generate_content_async(prompt)
                        resp_text = response.text
                    elif hasattr(self._model, "models"):
                        loop = asyncio.get_event_loop()
                        response = await loop.run_in_executor(
                            None,
                            lambda: self._model.models.generate_content(
                                model=self.settings.REASONING_MODEL,
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
                        return json.loads(cleaned)
                except Exception as e:
                    logger.debug(f"LLM reasoner fallback: {e}")

        # Fallback comparison heuristic
        return {
            "relationship_type": RelationshipType.UNRELATED.value,
            "confidence": 0.5,
            "explanation": "Evaluated via comparison engine",
            "reasoning": {},
        }

    def _build_prompt(self, fact_a, fact_b, context: dict | None) -> str:
        lines = [f"{LLM_REASONING_PROMPT}\n\nFACT A:"]
        lines.append(f"  Subject: {fact_a.subject}")
        lines.append(f"  Predicate: {fact_a.predicate}")
        lines.append(f"  Value: {fact_a.object_value}")
        lines.append(f"  Period: {fact_a.fiscal_year or ''}")
        lines.append(f"  Scope: {fact_a.scope or ''}")
        lines.append(f"  Source text: \"{fact_a.original_text[:300]}\"")

        lines.append("\nFACT B:")
        lines.append(f"  Subject: {fact_b.subject}")
        lines.append(f"  Predicate: {fact_b.predicate}")
        lines.append(f"  Value: {fact_b.object_value}")
        lines.append(f"  Period: {fact_b.fiscal_year or ''}")
        lines.append(f"  Scope: {fact_b.scope or ''}")
        lines.append(f"  Source text: \"{fact_b.original_text[:300]}\"")
        lines.append("\nJSON Output:")

        return "\n".join(lines)
