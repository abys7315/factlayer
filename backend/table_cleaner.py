"""Table artifact cleaner to strip auto-generated placeholder headers before LLM ingestion."""

from __future__ import annotations
import re

ARTIFACT_PATTERNS = [
    re.compile(r"\(?Column[_\s]?\d+\)?", re.IGNORECASE),
    re.compile(r"\(?Unnamed:?\s*\d+\)?", re.IGNORECASE),
    re.compile(r"\(?Field[_\s]?\d+\)?", re.IGNORECASE),
]


def strip_table_artifacts(text: str) -> str:
    """Remove auto-generated column/field placeholder labels from any text
    that will be shown to a user or fed to the LLM as a fact source."""
    if not text:
        return ""
    cleaned = text
    for pattern in ARTIFACT_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    # collapse leftover double spaces / stray punctuation from the removal
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\(\s*\)", "", cleaned)
    cleaned = re.sub(r"\s+([.,:;])", r"\1", cleaned)
    return cleaned.strip()


def clean_table_headers(headers: list[str]) -> list[str]:
    """
    Run this on your table parser's output BEFORE building the markdown
    table you send to the LLM. Placeholder headers get replaced with a
    neutral marker so the LLM knows to infer meaning from context rather
    than parroting "Column_16" into a fact statement.
    """
    cleaned = []
    for h in headers:
        h_str = str(h)
        is_artifact = any(p.search(h_str) for p in ARTIFACT_PATTERNS)
        cleaned.append("[unlabeled column — infer from context]" if is_artifact else h_str)
    return cleaned
