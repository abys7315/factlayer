"""Page model with classification for adaptive extraction."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, Text, Float, Integer, Boolean, DateTime, ForeignKey
from app.models.types import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Page classification for adaptive extraction
    page_type: Mapped[str] = mapped_column(String(30), default="text")
    fact_density: Mapped[float] = mapped_column(Float, default=0.5)
    table_density: Mapped[float] = mapped_column(Float, default=0.0)
    image_density: Mapped[float] = mapped_column(Float, default=0.0)
    text_density: Mapped[float] = mapped_column(Float, default=1.0)
    processing_priority: Mapped[int] = mapped_column(Integer, default=3)

    # Page dimensions (for bbox coordinate transformation)
    width: Mapped[float] = mapped_column(Float, default=612.0)
    height: Mapped[float] = mapped_column(Float, default=792.0)

    # OCR state
    ocr_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Raw content
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_blocks: Mapped[dict | None] = mapped_column(JSON(), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="pages")
    blocks = relationship("ContentBlock", back_populates="page", cascade="all, delete-orphan")
    figures = relationship("Figure", back_populates="page", cascade="all, delete-orphan")
    evidence_records = relationship("Evidence", back_populates="page")
