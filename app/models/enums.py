"""Enumerations used across the application models."""

from __future__ import annotations

import enum


class ProcessingStatus(str, enum.Enum):
    """Document processing lifecycle states."""

    QUEUED = "QUEUED"
    PARSING = "PARSING"
    OCR = "OCR"
    CONTEXT = "CONTEXT"
    DETECTION = "DETECTION"
    EXTRACTING = "EXTRACTING"
    VALIDATION = "VALIDATION"
    NORMALIZING = "NORMALIZING"
    RESOLVING = "RESOLVING"
    DEDUPLICATING = "DEDUPLICATING"
    EMBEDDING = "EMBEDDING"
    LINKING = "LINKING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# Ordered pipeline stages for resume-from-failure
PIPELINE_STAGES: list[str] = [
    ProcessingStatus.PARSING.value,
    ProcessingStatus.OCR.value,
    ProcessingStatus.CONTEXT.value,
    ProcessingStatus.DETECTION.value,
    ProcessingStatus.EXTRACTING.value,
    ProcessingStatus.VALIDATION.value,
    ProcessingStatus.NORMALIZING.value,
    ProcessingStatus.RESOLVING.value,
    ProcessingStatus.DEDUPLICATING.value,
    ProcessingStatus.EMBEDDING.value,
    ProcessingStatus.LINKING.value,
]


class BlockType(str, enum.Enum):
    TEXT = "TEXT"
    PARAGRAPH = "PARAGRAPH"
    PAGE_HEADER = "PAGE_HEADER"
    PAGE_FOOTER = "PAGE_FOOTER"
    TABLE = "TABLE"
    LIST = "LIST"
    HEADING = "HEADING"
    FOOTNOTE = "FOOTNOTE"
    CAPTION = "CAPTION"
    FIGURE_REF = "FIGURE_REF"


class FigureType(str, enum.Enum):
    DECORATIVE = "DECORATIVE"
    PHOTOGRAPH = "PHOTOGRAPH"
    CHART = "CHART"
    GRAPH = "GRAPH"
    DIAGRAM = "DIAGRAM"
    SCANNED_CONTENT = "SCANNED_CONTENT"
    UNKNOWN = "UNKNOWN"


class FactType(str, enum.Enum):
    EXTRACTED = "EXTRACTED"
    DERIVED = "DERIVED"


class FactStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    DISPUTED = "DISPUTED"
    RETRACTED = "RETRACTED"


class ProvenanceQuality(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EvidenceType(str, enum.Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    DERIVED = "DERIVED"


class RelationshipType(str, enum.Enum):
    CORROBORATES = "CORROBORATES"
    CONTRADICTS = "CONTRADICTS"
    CONTEXTUAL_DIFFERENCE = "CONTEXTUAL_DIFFERENCE"
    SUPERSEDES = "SUPERSEDES"
    UNCERTAIN = "UNCERTAIN"
    UNRELATED = "UNRELATED"


class EntityMatchConfidence(str, enum.Enum):
    MATCH = "MATCH"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    NO_MATCH = "NO_MATCH"


class JobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
