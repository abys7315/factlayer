"""Relationship model with multi-hypothesis classification and reasoning traces."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import String, Text, Float, Boolean, DateTime, Date, ForeignKey, Index
from app.models.types import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class FactRelationship(Base):
    __tablename__ = "fact_relationships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    fact_a_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("facts.id", ondelete="CASCADE"), nullable=False, index=True)
    fact_b_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("facts.id", ondelete="CASCADE"), nullable=False, index=True)

    # Core relationship classification
    relationship_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    classification_method: Mapped[str] = mapped_column(String(30), default="deterministic")  # deterministic, temporal, llm, human

    # Reasoning trace (structured explanation of how classification was reached)
    reasoning_trace: Mapped[dict] = mapped_column(JSON(), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    # Context difference subtype (when relationship_type == CONTEXTUAL_DIFFERENCE)
    context_difference_type: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Supersession tracking (when relationship_type == SUPERSEDES)
    supersession_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    superseded_by_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), nullable=True)

    # LLM audit trail (for non-deterministic classifications)
    llm_prompt_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    llm_raw_response: Mapped[dict | None] = mapped_column(JSON(), nullable=True)

    # Supporting evidence references
    supporting_evidence_a: Mapped[list | None] = mapped_column(JSON(), nullable=True)
    supporting_evidence_b: Mapped[list | None] = mapped_column(JSON(), nullable=True)
    classifier_version: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Review state
    is_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    fact_a = relationship("Fact", foreign_keys=[fact_a_id], backref="relationships_as_a")
    fact_b = relationship("Fact", foreign_keys=[fact_b_id], backref="relationships_as_b")
