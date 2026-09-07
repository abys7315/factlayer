"""Document section hierarchy model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from app.models.types import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class DocumentSection(Base):
    __tablename__ = "document_sections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_section_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), ForeignKey("document_sections.id", ondelete="SET NULL"), nullable=True)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    section_type: Mapped[str] = mapped_column(String(50), default="body")
    hierarchy_level: Mapped[int] = mapped_column(Integer, default=1)
    hierarchy_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    context_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="sections")
    parent = relationship("DocumentSection", remote_side=[id], backref="subsections")
    blocks = relationship("ContentBlock", back_populates="section")
    figures = relationship("Figure", back_populates="section")
