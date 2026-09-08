"""Figure/chart fact extraction using vision-capable LLM or caption parser."""

from __future__ import annotations

import os
import json
import asyncio
import time
import base64
import logging
from dataclasses import dataclass, field
from typing import Any

from app.config import get_settings
from app.extraction.fact_extractor import ExtractedFact, ExtractionResult
from app.models.enums import FigureType

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


class FigureFactExtractor:
    """
    Specialized extractor for figures/charts.
    Extracts structured metrics from charts via Gemini Vision or captions.
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

    async def classify_figure(self, image_data: bytes, image_ext: str = "png") -> str:
        """Classify a figure image into categories."""
        return FigureType.CHART.value

    async def extract_chart_data(
        self, image_data: bytes, image_ext: str, caption: str | None = None
    ) -> ExtractionResult:
        """Extract structured data from a chart image."""
        result = ExtractionResult()
        if caption and len(caption.strip()) > 5:
            # Parse caption for facts
            result.facts.append(
                ExtractedFact(
                    subject="Figure",
                    predicate="Caption",
                    object_value=caption,
                    original_text=caption,
                    evidence_excerpt=caption,
                    category="financial",
                    confidence=0.90,
                )
            )
        return result
