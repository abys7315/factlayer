"""Evidence model — character-exact grounding to source document."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, Text, Float, Integer, Boolean, DateTime, ForeignKey, Index
from app.models.types import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class Evidence(Base):
    __tablename__ = "fact_evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    fact_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("facts.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("document_pages.id", ondelete="CASCADE"), nullable=False)
    block_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), ForeignKey("content_blocks.id", ondelete="SET NULL"), nullable=True)
    figure_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), ForeignKey("figures.id", ondelete="SET NULL"), nullable=True)

    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    page_width: Mapped[float | None] = mapped_column(Float, nullable=True)
    page_height: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_type: Mapped[str] = mapped_column(String(30), default="primary")

    # Normalized bounding box [x0, y0, x1, y1] in [0.0, 1.0] coordinates
    bbox_x0: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y0: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_x1: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y1: Mapped[float] = mapped_column(Float, nullable=False)

    # Character offsets in block/page text
    char_offset_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_offset_end: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Verbatim excerpt from source
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)

    # Surrounding context window (+/- 2 sentences / lines)
    surrounding_context: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Source classification
    source_type: Mapped[str] = mapped_column(String(30), default="text")  # text, table_cell, heading, footnote, caption, figure
    table_cell_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    table_cell_col: Mapped[int | None] = mapped_column(Integer, nullable=True)
    table_header_context: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Validation state
    is_validated: Mapped[bool] = mapped_column(Boolean, default=True)
    validation_method: Mapped[str | None] = mapped_column(String(50), nullable=True)  # exact_match, fuzzy_match, table_structure, ocr_fuzzy
    validation_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    fact = relationship("Fact", back_populates="evidence_records")
    document = relationship("Document", back_populates="evidence_records")
    page = relationship("DocumentPage", back_populates="evidence_records")
    block = relationship("ContentBlock", back_populates="evidence_records")
    figure = relationship("Figure", back_populates="evidence_records")
