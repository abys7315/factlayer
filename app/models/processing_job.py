"""Processing job model for tracking pipeline execution and stage progress."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, Text, Float, Integer, DateTime, ForeignKey, Index
from app.models.types import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    current_stage: Mapped[str | None] = mapped_column(String(30), nullable=True)
    completed_stages: Mapped[dict] = mapped_column(JSON(), default=list)

    # Metrics
    stage_latencies: Mapped[dict] = mapped_column(JSON(), default=dict)
    llm_call_count: Mapped[int] = mapped_column(Integer, default=0)
    llm_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    llm_cost_estimate_usd: Mapped[float] = mapped_column(Float, default=0.0)

    # Results summary
    facts_extracted: Mapped[int] = mapped_column(Integer, default=0)
    facts_normalized: Mapped[int] = mapped_column(Integer, default=0)
    relationships_created: Mapped[int] = mapped_column(Integer, default=0)
    contradictions_found: Mapped[int] = mapped_column(Integer, default=0)
    supersessions_found: Mapped[int] = mapped_column(Integer, default=0)

    # Error handling
    error_stage: Mapped[str | None] = mapped_column(String(30), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="processing_jobs")
