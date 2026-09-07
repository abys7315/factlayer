"""Evidence validator — verifies LLM-extracted evidence exists in source."""

from __future__ import annotations

import re
import difflib
from dataclasses import dataclass

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
    fuzz = None


@dataclass
class ValidationResult:
    """Result of evidence validation."""
    is_valid: bool
    method: str  # exact_match, normalized_match, fuzzy_match, ocr_fuzzy, not_found
    score: float  # 0.0-1.0
    matched_text: str | None = None


class EvidenceValidator:
    """
    Validates that extracted evidence actually exists in the source document.
    Safety layer preventing hallucinated evidence.
    """

    FUZZY_THRESHOLD = 80.0
    OCR_FUZZY_THRESHOLD = 75.0

    def validate(self, extracted_evidence: str, source_text: str) -> ValidationResult:
        """Validate that extracted evidence exists in the source text."""
        if not extracted_evidence or not source_text:
            return ValidationResult(
                is_valid=False, method="not_found", score=0.0,
            )

        evidence = extracted_evidence.strip()
        source = source_text

        # 1. Exact match
        if evidence in source:
            return ValidationResult(
                is_valid=True, method="exact_match", score=1.0,
                matched_text=evidence,
            )

        # 2. Normalized match (strip extra whitespace, normalize unicode)
        norm_evidence = self._normalize(evidence)
        norm_source = self._normalize(source)

        if norm_evidence in norm_source:
            return ValidationResult(
                is_valid=True, method="normalized_match", score=0.95,
                matched_text=evidence,
            )

        # 3. Word-level overlap match
        ev_words = set(norm_evidence.split())
        src_words = set(norm_source.split())
        if ev_words and ev_words.issubset(src_words):
            return ValidationResult(
                is_valid=True, method="normalized_match", score=0.90,
                matched_text=evidence,
            )

        # 4. Fuzzy match
        fuzzy_score = self._compute_similarity(norm_evidence, norm_source)
        if fuzzy_score >= self.FUZZY_THRESHOLD:
            return ValidationResult(
                is_valid=True, method="fuzzy_match", score=fuzzy_score / 100.0,
                matched_text=evidence,
            )

        # 5. OCR fuzzy match (more lenient for OCR artifacts)
        ocr_evidence = self._ocr_normalize(evidence)
        ocr_source = self._ocr_normalize(source)

        if ocr_evidence in ocr_source:
            return ValidationResult(
                is_valid=True, method="ocr_fuzzy", score=0.85,
                matched_text=evidence,
            )

        ocr_fuzzy = self._compute_similarity(ocr_evidence, ocr_source)
        if ocr_fuzzy >= self.OCR_FUZZY_THRESHOLD:
            return ValidationResult(
                is_valid=True, method="ocr_fuzzy", score=ocr_fuzzy / 100.0,
                matched_text=evidence,
            )

        # 6. Fallback if evidence is short and contains key words
        if len(ev_words) >= 2 and len(ev_words.intersection(src_words)) / len(ev_words) >= 0.7:
            return ValidationResult(
                is_valid=True, method="word_overlap", score=0.75,
                matched_text=evidence,
            )

        return ValidationResult(
            is_valid=False, method="not_found", score=0.0,
        )

    def _normalize(self, text: str) -> str:
        """Normalize whitespace and common punctuation."""
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace('"', '"').replace('"', '"').replace("'", "'").replace("'", "'")
        text = text.replace('–', '-').replace('—', '-')
        return text.lower()

    def _ocr_normalize(self, text: str) -> str:
        """More aggressive normalization for OCR artifacts."""
        text = self._normalize(text)
        text = re.sub(r'[^\w\s$€£₹%.]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _compute_similarity(self, needle: str, haystack: str) -> float:
        """Compute fuzzy similarity ratio (0.0 to 100.0)."""
        if HAS_RAPIDFUZZ and fuzz is not None:
            return float(fuzz.partial_ratio(needle, haystack))
        
        # SequenceMatcher fallback
        if len(needle) > len(haystack):
            needle, haystack = haystack, needle
        
        # Check in sliding windows around needle length
        n_len = len(needle)
        if n_len == 0:
            return 0.0
        
        max_ratio = 0.0
        step = max(1, n_len // 4)
        for i in range(0, max(1, len(haystack) - n_len + 1), step):
            window = haystack[i:i + n_len * 2]
            ratio = difflib.SequenceMatcher(None, needle, window).ratio() * 100.0
            if ratio > max_ratio:
                max_ratio = ratio
                if max_ratio >= 95.0:
                    break
        return max_ratio

    def validate_batch(
        self, evidence_texts: list[str], source_text: str
    ) -> list[ValidationResult]:
        """Validate multiple evidence texts against the same source."""
        return [self.validate(ev, source_text) for ev in evidence_texts]
