"""Rule-based candidate detection to minimize LLM calls."""

from __future__ import annotations

import re
from app.parsing.pdf_parser import ParsedBlock
from app.models.enums import BlockType


class CandidateDetector:
    """
    Scans blocks for fact-bearing signals and assigns priority scores.
    Only blocks exceeding the threshold are sent to LLM extraction.
    """

    THRESHOLD = 0.10

    # Patterns indicating fact-bearing content
    NUMERIC_PATTERN = re.compile(
        r'[\$€£₹¥]\s*[\d,]+(?:\.\d+)?|'
        r'\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:million|billion|trillion|mn|bn|tn|crore|cr|lakh|lac|k|m|b|%|percent|per\s+cent|bps|basis\s+points|points|pts|mark)\b|'
        r'\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|'
        r'\b\d+(?:\.\d+)?\s*(?:%|percent|per\s+cent|bps)\b',
        re.IGNORECASE,
    )

    ENTITY_PATTERN = re.compile(
        r'\b[A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*)+\b'  # Proper nouns / multi-word entities
    )

    TEMPORAL_PATTERN = re.compile(
        r'\b(?:FY|CY|fiscal\s+year|quarter|Q[1-4]|H[12])[:\s-]*\d{2,4}(?:-\d{2,4})?\b|'
        r'\b(?:20\d{2}(?:-\d{2,4})?|19\d{2})\b|'
        r'\b(?:end-)?(?:January|February|March|April|May|June|July|August|September|October|November|December)(?:\s+\d{1,2}(?:st|nd|rd|th)?,?)?\s+\d{4}\b|'
        r'\bQ[1-4]\b',
        re.IGNORECASE,
    )

    ACTION_PATTERN = re.compile(
        r'\b(?:increased|decreased|grew|declined|rose|fell|dropped|surged|'
        r'appointed|resigned|retired|joined|acquired|merged|divested|'
        r'announced|reported|achieved|exceeded|launched|completed|signed|'
        r'approved|ratified|amended|established|purchases|sales|traded|rebounded|'
        r'breached|touched|rallied|maintained|exhibited|pared)\b',
        re.IGNORECASE,
    )

    DEFINITIVE_PATTERN = re.compile(
        r'\b(?:was|were|is|are|has been|have been|will be|became|'
        r'totaled|amounted to|stood at|reached|recorded|touched|exhibited|breached)\b',
        re.IGNORECASE,
    )

    def score_block(self, block: ParsedBlock) -> float:
        """Compute fact-bearing candidate score for a block. Returns 0.0-1.0."""
        if not block.content or len(block.content.strip()) < 10:
            return 0.0

        content = block.content
        score = 0.0

        # Tables always get highest score
        if block.block_type == BlockType.TABLE.value:
            return 0.95

        # Headings get moderate score (useful as context, sometimes contain facts)
        if block.block_type == BlockType.HEADING.value:
            return 0.30

        # Footnotes get moderate score (often contain important qualifications)
        if block.block_type == BlockType.FOOTNOTE.value:
            score += 0.25

        # Standard body paragraph with substantial content gets base score
        if block.block_type == BlockType.PARAGRAPH.value and len(content.strip()) > 40:
            score += 0.15

        # Numeric values (strongest signal)
        numeric_matches = len(self.NUMERIC_PATTERN.findall(content))
        score += min(0.40, numeric_matches * 0.15)

        # Named entities
        entity_matches = len(self.ENTITY_PATTERN.findall(content))
        score += min(0.20, entity_matches * 0.05)

        # Temporal references
        temporal_matches = len(self.TEMPORAL_PATTERN.findall(content))
        score += min(0.20, temporal_matches * 0.10)

        # Action/change verbs
        action_matches = len(self.ACTION_PATTERN.findall(content))
        score += min(0.15, action_matches * 0.08)

        # Definitive statements
        definitive_matches = len(self.DEFINITIVE_PATTERN.findall(content))
        score += min(0.10, definitive_matches * 0.05)

        return min(1.0, score)

    def detect_candidates(
        self, blocks: list[ParsedBlock], priority_boost: float = 0.0
    ) -> list[tuple[ParsedBlock, float]]:
        """
        Score all blocks and return those above threshold.
        priority_boost: added to scores for high-priority pages.
        """
        candidates = []
        for block in blocks:
            score = self.score_block(block) + priority_boost
            if score >= self.THRESHOLD:
                candidates.append((block, min(1.0, score)))

        # Sort by score descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates
