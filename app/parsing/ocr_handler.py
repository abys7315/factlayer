"""Selective OCR handler with concurrency control."""

from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass

import fitz  # pymupdf
from PIL import Image

from app.config import get_settings


@dataclass
class OCRResult:
    """Result of OCR processing."""
    text: str
    confidence: float
    was_applied: bool


class OCRHandler:
    """
    Selective OCR with concurrency control.

    Strategy:
    1. If text quality score < threshold → apply OCR
    2. Render page to image via pymupdf
    3. Run pytesseract
    4. Return OCR text with confidence
    """

    # Text quality threshold — below this, OCR is triggered
    QUALITY_THRESHOLD = 0.3

    def __init__(self):
        settings = get_settings()
        self._semaphore = asyncio.Semaphore(settings.OCR_CONCURRENCY)
        self._render_dpi = 300

    async def process_page_if_needed(
        self, page_data: bytes, page_number: int, text_quality: float, existing_text: str
    ) -> OCRResult:
        """Apply OCR only if text quality is below threshold."""
        if text_quality >= self.QUALITY_THRESHOLD and len(existing_text.strip()) > 30:
            return OCRResult(text=existing_text, confidence=text_quality, was_applied=False)

        async with self._semaphore:
            return await self._run_ocr(page_data, page_number)

    async def _run_ocr(self, pdf_data: bytes, page_number: int) -> OCRResult:
        """Render page and run OCR."""
        try:
            # Run OCR in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._ocr_sync, pdf_data, page_number)
            return result
        except Exception as e:
            return OCRResult(text="", confidence=0.0, was_applied=True)

    def _ocr_sync(self, pdf_data: bytes, page_number: int) -> OCRResult:
        """Synchronous OCR processing."""
        try:
            import pytesseract

            # Render page to image
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            page = doc[page_number - 1]
            mat = fitz.Matrix(self._render_dpi / 72, self._render_dpi / 72)
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            doc.close()

            # Run tesseract
            ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

            # Extract text and compute confidence
            texts = []
            confidences = []
            for i, text in enumerate(ocr_data.get("text", [])):
                conf = ocr_data["conf"][i]
                if isinstance(conf, (int, float)) and conf > 0 and text.strip():
                    texts.append(text)
                    confidences.append(conf)

            full_text = " ".join(texts)
            avg_confidence = sum(confidences) / len(confidences) / 100.0 if confidences else 0.0

            return OCRResult(text=full_text, confidence=avg_confidence, was_applied=True)

        except ImportError:
            # pytesseract not available — return empty
            return OCRResult(text="", confidence=0.0, was_applied=True)
        except Exception:
            return OCRResult(text="", confidence=0.0, was_applied=True)
