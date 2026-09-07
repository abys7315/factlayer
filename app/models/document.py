"""Document model with full context, processing state, and versioning."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    String, Text, Float, Integer, Boolean, DateTime, Date, Index,
)
from app.models.types import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base
from app.models.enums import ProcessingStatus


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Document-level context (populated by Document Context Resolver)
    organization: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    document_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reporting_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    reporting_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    default_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    geography: Mapped[str | None] = mapped_column(String(100), nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Source metadata
    source_priority: Mapped[float] = mapped_column(Float, default=0.5)
    source_metadata: Mapped[dict | None] = mapped_column(JSON(), nullable=True)

    # Processing state
    status: Mapped[str] = mapped_column(
        String(30), default=ProcessingStatus.QUEUED.value, nullable=False, index=True,
    )
    current_stage: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_successful_stage: Mapped[str | None] = mapped_column(String(30), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pipeline versioning
    pipeline_version: Mapped[str] = mapped_column(String(30), default="v1.0.0")
    extractor_version: Mapped[str] = mapped_column(String(30), default="v1.0.0")
    normalizer_version: Mapped[str] = mapped_column(String(30), default="v1.0.0")
    prompt_version: Mapped[str] = mapped_column(String(30), default="2026-09-07")
    model_name: Mapped[str] = mapped_column(String(100), default="gemini-2.5-flash")
    embedding_model: Mapped[str] = mapped_column(String(100), default="text-embedding-004")

    # Processing metrics
    llm_calls_count: Mapped[int] = mapped_column(Integer, default=0)
    llm_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    llm_total_latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processing_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")
    sections = relationship("DocumentSection", back_populates="document", cascade="all, delete-orphan")
    blocks = relationship("ContentBlock", back_populates="document", cascade="all, delete-orphan")
    facts = relationship("Fact", back_populates="document", cascade="all, delete-orphan")
    figures = relationship("Figure", back_populates="document", cascade="all, delete-orphan")
    evidence_records = relationship("Evidence", back_populates="document", cascade="all, delete-orphan")
    processing_jobs = relationship("ProcessingJob", back_populates="document", cascade="all, delete-orphan")
