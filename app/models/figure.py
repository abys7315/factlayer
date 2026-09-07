"""Figure / Chart model with extracted data and visual reasoning."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, Text, Float, Boolean, DateTime, ForeignKey
from app.models.types import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class Figure(Base):
    __tablename__ = "figures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("document_pages.id", ondelete="CASCADE"), nullable=False)
    section_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), ForeignKey("document_sections.id", ondelete="SET NULL"), nullable=True)

    figure_type: Mapped[str] = mapped_column(String(30), default="chart")
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Coordinates [x0, y0, x1, y1]
    bbox_x0: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y0: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_x1: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y1: Mapped[float] = mapped_column(Float, nullable=False)

    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    surrounding_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Chart reasoning output
    extracted_data: Mapped[dict | None] = mapped_column(JSON(), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning_trace: Mapped[dict | None] = mapped_column(JSON(), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    # State
    is_ambiguous: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_cross_ref: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="figures")
    page = relationship("DocumentPage", back_populates="figures")
    section = relationship("DocumentSection", back_populates="figures")
    evidence_records = relationship("Evidence", back_populates="figure")
