"""Canonical entity and alias models for multi-hypothesis resolution."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, Text, Float, DateTime, ForeignKey, Index
from app.models.types import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # ORG, PERSON, GPE, PRODUCT, CONCEPT

    # Knowledge graph metadata
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    attributes: Mapped[dict | None] = mapped_column(JSON(), nullable=True)

    # Resolution metadata
    resolution_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    resolution_method: Mapped[str] = mapped_column(String(50), default="exact")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    aliases = relationship("EntityAlias", back_populates="entity", cascade="all, delete-orphan")
    facts = relationship("Fact", back_populates="entity")


class EntityAlias(Base):
    __tablename__ = "entity_aliases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    alias_type: Mapped[str] = mapped_column(String(50), default="variant")  # abbreviation, ticker, former_name, misspelled
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    entity = relationship("Entity", back_populates="aliases")
