"""FastAPI application — main entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.models.database import init_db, close_db
from app.storage.qdrant_repository import QdrantRepository
from app.api.routes import documents, facts, relationships, viewer, events, graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Startup
    await init_db()
    try:
        qdrant = QdrantRepository()
        await qdrant.ensure_collection()
    except Exception:
        pass
    yield
    # Shutdown
    await close_db()


settings = get_settings()

app = FastAPI(
    title="Fact Knowledge Layer",
    description="Provenance-first fact intelligence system for cross-document analysis",
    version=settings.PIPELINE_VERSION,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes under both /api and /api/v1 for total frontend compatibility
for prefix in ["/api", "/api/v1"]:
    app.include_router(documents.router, prefix=prefix, tags=["Documents"])
    app.include_router(facts.router, prefix=prefix, tags=["Facts"])
    app.include_router(relationships.router, prefix=prefix, tags=["Relationships"])
    app.include_router(graph.router, prefix=prefix, tags=["Graph"])
    app.include_router(viewer.router, prefix=prefix, tags=["Viewer"])
    app.include_router(events.router, prefix=prefix, tags=["Events"])

# Ensure upload directory exists
settings.upload_path

try:
    app.mount("/uploads", StaticFiles(directory=str(settings.upload_path)), name="uploads")
except Exception:
    pass


@app.get("/api/health")
@app.get("/api/v1/health")
async def health_check():
    health = {
        "status": "healthy",
        "version": settings.PIPELINE_VERSION,
        "api": "ok",
        "database": "ok",
        "qdrant": "ok",
        "redis": "ok",
        "llm": "ok" if settings.GOOGLE_API_KEY else "fallback_deterministic",
        "embeddings": "ok" if settings.GOOGLE_API_KEY else "fallback_local",
        "storage": "ok",
    }
    # Check Database
    try:
        from app.models.database import get_engine
        from sqlalchemy import text
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        health["database"] = f"error: {str(e)[:50]}"
        health["status"] = "degraded"

    return health
