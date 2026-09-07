"""Content block model for fine-grained provenance."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, Text, Float, Integer, DateTime, ForeignKey, Index
from app.models.types import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class ContentBlock(Base):
    __tablename__ = "content_blocks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("document_pages.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), ForeignKey("document_sections.id", ondelete="SET NULL"), nullable=True)

    block_type: Mapped[str] = mapped_column(String(30), nullable=False)
    block_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Coordinates [x0, y0, x1, y1] normalized to page dimensions
    bbox_x0: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y0: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_x1: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y1: Mapped[float] = mapped_column(Float, nullable=False)

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reading_order_index: Mapped[int] = mapped_column(Integer, default=0)

    # Structural metadata (font, style, table structure)
    structural_metadata: Mapped[dict | None] = mapped_column(JSON(), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="blocks")
    page = relationship("DocumentPage", back_populates="blocks")
    section = relationship("DocumentSection", back_populates="blocks")
    evidence_records = relationship("Evidence", back_populates="block")
