"""Pydantic schemas for API request and response validation."""

from __future__ import annotations
from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field


class DocumentBase(BaseModel):
    filename: str
    page_count: int = 0


class DocumentCreate(DocumentBase):
    pass


class DocumentResponse(DocumentBase):
    id: int
    upload_date: datetime
    raw_text_path: Optional[str] = None

    class Config:
        from_attributes = True


class FactBase(BaseModel):
    fact_text: str
    fact_type: Optional[str] = "general"
    fact_type_reasoning: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    time_period: Optional[str] = None
    source_quote: str
    page_number: int
    bbox: Optional[List[float]] = None


class FactCreate(FactBase):
    doc_id: int
    embedding: Optional[List[float]] = None


class FactResponse(FactBase):
    id: int
    doc_id: int
    created_at: datetime
    document_filename: Optional[str] = None

    class Config:
        from_attributes = True


class RelationshipBase(BaseModel):
    fact_id_1: int
    fact_id_2: int
    relationship_type: str  # corroborate | contradict | reconcilable | unrelated
    reconciling_factors: Optional[List[str]] = []
    explanation: str
    confidence: float = 1.0


class RelationshipCreate(RelationshipBase):
    pass


class RelationshipResponse(RelationshipBase):
    id: int
    created_at: datetime
    fact_1: Optional[FactResponse] = None
    fact_2: Optional[FactResponse] = None

    class Config:
        from_attributes = True


class FactDetailResponse(FactResponse):
    document: Optional[DocumentResponse] = None
    relationships: List[RelationshipResponse] = []


class FailureLogResponse(BaseModel):
    id: int
    error_type: str
    details: str
    page_number: Optional[int] = None
    fact_id: Optional[int] = None
    context: Optional[dict] = {}
    timestamp: str

    class Config:
        from_attributes = True


class FailureReportResponse(BaseModel):
    total_failures_logged: int
    failures_by_type: dict
    logs: List[FailureLogResponse]
    audit_timestamp: str
    status: str


class UploadResponse(BaseModel):
    document_id: int
    filename: str
    page_count: int
    facts_extracted: int
    relationships_found: int
    status: str = "success"
