"""Application configuration via Pydantic Settings."""

from __future__ import annotations

import os
import json
from pathlib import Path
from functools import lru_cache

try:
    from pydantic_settings import BaseSettings
except Exception:
    from pydantic import BaseModel as BaseSettings

from pydantic import field_validator


class Settings(BaseSettings):
    """Central configuration – all values sourced from environment / .env."""

    # ── Database ──────────────────────────────────────────────────────
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://superjoin:superjoin@localhost:5432/factlayer")
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "facts")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # ── LLM ───────────────────────────────────────────────────────────
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    EXTRACTION_MODEL: str = os.getenv("EXTRACTION_MODEL", "gemini-2.5-flash")
    REASONING_MODEL: str = os.getenv("REASONING_MODEL", "gemini-2.5-pro")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-004")
    EMBEDDING_DIMENSIONS: int = int(os.getenv("EMBEDDING_DIMENSIONS", "768"))

    # ── LLM Cost / Latency Controls ──────────────────────────────────
    MAX_LLM_REQUESTS_PER_DOCUMENT: int = int(os.getenv("MAX_LLM_REQUESTS_PER_DOCUMENT", "50"))
    MAX_CONCURRENT_LLM_REQUESTS: int = int(os.getenv("MAX_CONCURRENT_LLM_REQUESTS", "5"))
    EXTRACTION_BATCH_SIZE: int = int(os.getenv("EXTRACTION_BATCH_SIZE", "10"))
    MAX_CONTEXT_TOKENS: int = int(os.getenv("MAX_CONTEXT_TOKENS", "8192"))
    LLM_REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "30"))
    LLM_RETRY_MAX: int = int(os.getenv("LLM_RETRY_MAX", "3"))
    LLM_RETRY_BACKOFF_SECONDS: int = int(os.getenv("LLM_RETRY_BACKOFF_SECONDS", "2"))

    # ── Processing Limits ─────────────────────────────────────────────
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "100"))
    MAX_PAGES: int = int(os.getenv("MAX_PAGES", "500"))
    MAX_PROCESSING_SECONDS: int = int(os.getenv("MAX_PROCESSING_SECONDS", "600"))
    WORKER_CONCURRENCY: int = int(os.getenv("WORKER_CONCURRENCY", "4"))
    OCR_CONCURRENCY: int = int(os.getenv("OCR_CONCURRENCY", "2"))
    EMBEDDING_CONCURRENCY: int = int(os.getenv("EMBEDDING_CONCURRENCY", "3"))

    # ── Comparison Tolerances ─────────────────────────────────────────
    NUMERIC_TOLERANCE_EQUIVALENT: float = float(os.getenv("NUMERIC_TOLERANCE_EQUIVALENT", "0.005"))
    NUMERIC_TOLERANCE_ROUNDING: float = float(os.getenv("NUMERIC_TOLERANCE_ROUNDING", "0.05"))
    NUMERIC_TOLERANCE_CONTRADICTION: float = float(os.getenv("NUMERIC_TOLERANCE_CONTRADICTION", "0.05"))

    # ── Pipeline Versioning ───────────────────────────────────────────
    PIPELINE_VERSION: str = os.getenv("PIPELINE_VERSION", "v1.0.0")
    EXTRACTOR_VERSION: str = os.getenv("EXTRACTOR_VERSION", "v1.0.0")
    NORMALIZER_VERSION: str = os.getenv("NORMALIZER_VERSION", "v1.0.0")
    PROMPT_VERSION: str = os.getenv("PROMPT_VERSION", "2026-09-07")

    # ── Security / Paths ──────────────────────────────────────────────
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    PROCESSING_DIR: str = os.getenv("PROCESSING_DIR", "./processing")
    ALLOWED_MIME_TYPES: str = os.getenv("ALLOWED_MIME_TYPES", "application/pdf")

    # ── Server ────────────────────────────────────────────────────────
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", '["http://localhost:5173"]')

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors(cls, v: str | list) -> str:
        if isinstance(v, list):
            return json.dumps(v)
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        try:
            return json.loads(self.CORS_ORIGINS)
        except Exception:
            return ["http://localhost:5173"]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def upload_path(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def processing_path(self) -> Path:
        p = Path(self.PROCESSING_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
