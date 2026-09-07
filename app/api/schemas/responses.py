"""Pydantic response schemas for all API endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Common ────────────────────────────────────────────────────────────

class APIResponse(BaseModel):
    success: bool = True
    message: str = ""
    data: Any = None


class PaginatedResponse(BaseModel):
    items: list[Any] = []
    total: int = 0
    limit: int = 100
    offset: int = 0


# ── Documents ─────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: str
    filename: str
    original_filename: str | None = None
    page_count: int = 1
    status: str = "COMPLETED"
    organization: str | None = None
    document_type: str | None = None
    document_title: str | None = None
    publication_date: date | None = None
    doc_date: str | None = None
    sha256_hash: str | None = None
    default_currency: str | None = None
    facts_count: int = 0
    relationships_count: int = 0
    context_summary: str | None = None
    created_at: datetime | None = None
    processing_completed_at: datetime | None = None

    model_config = {"from_attributes": True, "extra": "ignore"}


class DocumentDetailResponse(DocumentResponse):
    file_hash: str | None = None
    file_size_bytes: int | None = 0
    mime_type: str | None = "application/pdf"
    reporting_period_start: date | None = None
    reporting_period_end: date | None = None
    geography: str | None = None
    language: str | None = None
    source_priority: float = 0.5
    current_stage: str | None = None
    last_successful_stage: str | None = None
    retry_count: int = 0
    error_code: str | None = None
    error_message: str | None = None
    pipeline_version: str | None = "v1.0.0"
    extractor_version: str | None = "v1.0.0"
    model_name: str | None = "gemini-2.5-flash"
    llm_calls_count: int = 0
    llm_tokens_used: int = 0
    llm_total_latency_ms: int = 0
    processing_started_at: datetime | None = None


class ProcessingStatusResponse(BaseModel):
    document_id: str
    status: str
    current_stage: str | None = None
    last_successful_stage: str | None = None
    retry_count: int = 0
    error_code: str | None = None
    error_message: str | None = None
    facts_extracted: int = 0
    relationships_created: int = 0


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    page_count: int = 1
    message: str = "Document uploaded and queued for processing"


# ── Facts ─────────────────────────────────────────────────────────────

class EvidenceResponse(BaseModel):
    id: str
    evidence_id: str | None = None
    evidence_type: str | None = "text"
    source_type: str | None = "text"
    block_type: str | None = "text"
    excerpt: str | None = ""
    snippet: str | None = ""
    page_number: int = 1
    confidence: float | None = 0.95
    bbox: dict[str, float] | None = None
    bbox_x0: float | None = None
    bbox_y0: float | None = None
    bbox_x1: float | None = None
    bbox_y1: float | None = None
    is_validated: bool = True
    validation_method: str | None = "exact_match"
    validation_score: float | None = 1.0

    model_config = {"from_attributes": True, "extra": "ignore"}


class FactResponse(BaseModel):
    id: str
    document_id: str
    entity_name: str | None = None
    subject: str | None = None
    attribute: str | None = None
    predicate: str | None = None
    value_text: str | None = None
    object_value: str | None = None
    normalized_value: Any = None
    object_numeric: float | None = None
    unit: str | None = None
    original_text: str | None = ""
    fact_type: str | None = "EXTRACTED"
    category: str | None = "General"
    validity_start: str | None = None
    validity_end: str | None = None
    fiscal_year: str | None = None
    fiscal_quarter: str | None = None
    scope: str | None = None
    geography: str | None = None
    basis: str | None = None
    currency: str | None = None
    context_fingerprint: str = ""
    provenance_quality: str = "HIGH"
    confidence_score: float | None = 0.95
    confidence: float | None = 0.95
    is_uncertain: bool = False
    doc_date: str | None = None
    document_date: date | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True, "extra": "ignore"}


class FactDetailResponse(FactResponse):
    reporting_period_label: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    is_canonical: bool = True
    extractor_version: str | None = "v1.0.0"
    prompt_version: str | None = "2026-09-07"
    model_name: str | None = "gemini-2.5-flash"
    evidence: list[EvidenceResponse] = []


# ── Relationships ─────────────────────────────────────────────────────

class RelationshipResponse(BaseModel):
    id: str
    fact_a_id: str
    fact_b_id: str
    relationship_type: str
    confidence: float = 0.9
    confidence_score: float = 0.9
    engine: str = "llm_reasoner"
    classification_method: str = "deterministic"
    explanation: str = ""
    reconciling_factors: list[str] = []
    context_difference_type: str | None = None
    supersession_date: date | None = None
    reasoning_trace: dict[str, Any] | None = None
    fact_a: FactResponse | None = None
    fact_b: FactResponse | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True, "extra": "ignore"}


class RelationshipDetailResponse(RelationshipResponse):
    evidence_a: list[EvidenceResponse] = []
    evidence_b: list[EvidenceResponse] = []
    classifier_version: str = "v1.0.0"
    model_name: str | None = "gemini-2.5-pro"


# ── Dashboard & Viewer ────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_documents: int = 0
    total_facts: int = 0
    total_relationships: int = 0
    corroborations: int = 0
    contradictions: int = 0
    contextual_differences: int = 0
    superseded_facts: int = 0
    superseded: int = 0
    documents_processing: int = 0
    documents_completed: int = 0
    documents_failed: int = 0


class ViewerOverlayItem(BaseModel):
    fact_id: str
    evidence_id: str | None = None
    entity_name: str | None = None
    attribute: str | None = None
    value_text: str | None = None
    page_number: int = 1
    block_type: str | None = "text"
    confidence: float | None = 0.95
    snippet: str | None = ""
    bbox: dict[str, float] | None = None


class ViewerOverlayResponse(BaseModel):
    document_id: str
    page_count: int = 1
    overlays: list[ViewerOverlayItem] = []


class PaginatedFactList(BaseModel):
    items: list[FactResponse] = []
    total: int = 0


class PaginatedRelationshipList(BaseModel):
    items: list[RelationshipResponse] = []
    total: int = 0


class PaginatedDocumentList(BaseModel):
    items: list[DocumentResponse] = []
    total: int = 0
