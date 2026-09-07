"""SQLAlchemy models and database connection for SQLite."""

from __future__ import annotations
import os
import json
from pathlib import Path
from datetime import datetime
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    Text,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Determine database path (data/facts.db relative to root)
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "facts.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    upload_date = Column(DateTime, default=datetime.utcnow)
    page_count = Column(Integer, default=0)
    raw_text_path = Column(String(500), nullable=True)

    # Relationship to facts
    facts = relationship("Fact", back_populates="document", cascade="all, delete-orphan")


class Fact(Base):
    __tablename__ = "facts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    doc_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    fact_text = Column(Text, nullable=False)
    fact_type = Column(String(100), nullable=True, default="general")
    fact_type_reasoning = Column(Text, nullable=True)
    value = Column(Float, nullable=True)
    unit = Column(String(100), nullable=True)
    time_period = Column(String(100), nullable=True)
    source_quote = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=False)
    bbox = Column(Text, nullable=True)  # JSON-encoded array [x0, y0, x1, y1]
    embedding = Column(Text, nullable=True)  # JSON-encoded array of floats
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="facts")

    def get_bbox(self) -> list[float] | None:
        if self.bbox:
            try:
                return json.loads(self.bbox)
            except Exception:
                return None
        return None

    def set_bbox(self, box: list[float] | tuple[float, float, float, float] | None):
        if box is not None:
            self.bbox = json.dumps(list(box))
        else:
            self.bbox = None

    def get_embedding(self) -> list[float] | None:
        if self.embedding:
            try:
                return json.loads(self.embedding)
            except Exception:
                return None
        return None

    def set_embedding(self, emb: list[float]):
        self.embedding = json.dumps(emb)


class Relationship(Base):
    __tablename__ = "relationships"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    fact_id_1 = Column(Integer, ForeignKey("facts.id", ondelete="CASCADE"), nullable=False, index=True)
    fact_id_2 = Column(Integer, ForeignKey("facts.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = Column(String(50), nullable=False, index=True)  # corroborate | contradict | reconcilable | unrelated
    reconciling_factors = Column(Text, nullable=True)  # JSON-encoded array of factors
    explanation = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    fact_1 = relationship("Fact", foreign_keys=[fact_id_1])
    fact_2 = relationship("Fact", foreign_keys=[fact_id_2])

    def get_reconciling_factors(self) -> list[str]:
        if self.reconciling_factors:
            try:
                return json.loads(self.reconciling_factors)
            except Exception:
                return []
        return []

    def set_reconciling_factors(self, factors: list[str]):
        self.reconciling_factors = json.dumps(factors)


class FailureLog(Base):
    __tablename__ = "failure_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    error_type = Column(String(100), nullable=False, index=True)
    details = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    fact_id = Column(Integer, nullable=True)
    context_data = Column(Text, nullable=True)  # JSON-encoded
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    """Create all tables in the SQLite database."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI Dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
