"""Async SQLAlchemy engine and session factory."""

from __future__ import annotations

import os
from pathlib import Path
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        db_url = settings.DATABASE_URL
        # If database URL uses postgresql+asyncpg but asyncpg/postgres not available, fallback to SQLite
        if "postgresql" in db_url:
            try:
                import asyncpg
            except ImportError:
                db_url = "sqlite+aiosqlite:///./factlayer.db"

        if "sqlite" in db_url:
            _engine = create_async_engine(
                db_url,
                echo=False,
            )
        else:
            _engine = create_async_engine(
                db_url,
                echo=False,
                pool_size=20,
                max_overflow=10,
                pool_pre_ping=True,
            )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db() -> AsyncSession:
    """Dependency for FastAPI – yields an async session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Create all tables (for development; production uses Alembic)."""
    global _engine, _session_factory
    # Import all models so Base.metadata knows about them
    import app.models.document
    import app.models.page
    import app.models.section
    import app.models.block
    import app.models.figure
    import app.models.entity
    import app.models.fact
    import app.models.evidence
    import app.models.relationship
    import app.models.processing_job

    engine = get_engine()
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        if "postgresql" in str(engine.url):
            print(f"[WARN] PostgreSQL connection failed: {e}. Falling back to SQLite for production resilience.")
            await engine.dispose()
            _engine = create_async_engine("sqlite+aiosqlite:///./factlayer.db", echo=False)
            _session_factory = async_sessionmaker(
                bind=_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            async with _engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        else:
            raise


async def close_db():
    """Dispose of the engine connection pool."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
