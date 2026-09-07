"""Canonical fact model with rich context dimensions and versioning."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    String, Text, Float, Integer, Boolean, DateTime, Date, ForeignKey, Index,
)
from app.models.types import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base
from app.models.enums import FactStatus


class Fact(Base):
    __tablename__ = "facts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True)

    # Core claim: (Subject, Predicate, Object)
    subject: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    predicate: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    object_value: Mapped[str] = mapped_column(Text, nullable=False)
    object_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    object_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fact_type: Mapped[str] = mapped_column(String(30), default="EXTRACTED")

    # Temporal context
    fact_date_exact: Mapped[date | None] = mapped_column(Date, nullable=True)
    fact_time_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    fact_time_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    fiscal_year: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fiscal_quarter: Mapped[str | None] = mapped_column(String(10), nullable=True)
    reporting_period_label: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Reporting context
    scope: Mapped[str | None] = mapped_column(String(100), nullable=True)
    geography: Mapped[str | None] = mapped_column(String(100), nullable=True)
    basis: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Extraction confidence
    extraction_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.95)
    provenance_quality: Mapped[str] = mapped_column(String(20), default="high")
    is_uncertain: Mapped[bool] = mapped_column(Boolean, default=False)

    # Document-level context propagated
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_priority: Mapped[float] = mapped_column(Float, default=0.5)

    # Fingerprints & Hashes
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    context_fingerprint: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Original snippet
    original_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Status & Supersession
    status: Mapped[str] = mapped_column(
        String(20), default=FactStatus.ACTIVE.value, nullable=False, index=True,
    )
    superseded_by_fact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    supersession_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Deduplication & Canonicalization
    is_canonical: Mapped[bool] = mapped_column(Boolean, default=True)
    canonical_fact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), ForeignKey("facts.id", ondelete="SET NULL"), nullable=True)

    # Vector embedding state
    embedding_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Versioning
    extractor_version: Mapped[str] = mapped_column(String(30), default="v1.0.0")
    prompt_version: Mapped[str | None] = mapped_column(String(50), default="2026-09-07")
    model_name: Mapped[str | None] = mapped_column(String(100), default="gemini-2.5-flash")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="facts")
    entity = relationship("Entity", back_populates="facts")
    evidence_records = relationship("Evidence", back_populates="fact", cascade="all, delete-orphan")
    canonical_fact = relationship("Fact", remote_side=[id], backref="derived_facts")
