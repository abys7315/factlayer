"""Document routes — upload, list, detail, status, delete, stats."""

from __future__ import annotations

import uuid
import asyncio
import logging
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models import Document, Fact, FactRelationship, ProcessingStatus
from app.storage.postgres_repository import PostgresRepository
from app.storage.redis_manager import RedisManager
from app.security.upload_validator import UploadValidator
from app.api.schemas.responses import (
    DocumentResponse, DocumentDetailResponse, ProcessingStatusResponse,
    UploadResponse, DashboardStats, PaginatedDocumentList,
)

logger = logging.getLogger(__name__)

router = APIRouter()
validator = UploadValidator()
redis = RedisManager()


async def _run_pipeline_background(doc_id_str: str, file_path_str: str):
    """Execute document ingestion pipeline in the background and commit stages in real-time."""
    from app.workers.pipeline import IngestionPipeline
    p = IngestionPipeline()
    try:
        await p.process_document(doc_id_str, file_path_str)
    except Exception as e:
        logger.error(f"Background ingestion failed for doc {doc_id_str}: {e}", exc_info=True)


@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF document and process facts via real-time multi-stage pipeline."""
    file_data = await file.read()
    original_name = file.filename or "document.pdf"

    # Validate
    result = await validator.validate(file_data, original_name)
    if not result.is_valid:
        raise HTTPException(status_code=400, detail=result.rejection_reason)

    repo = PostgresRepository(db)
    file_path = await validator.save_file(file_data, result.sanitized_filename)

    # Check for existing record
    existing = await repo.get_document_by_hash(result.file_hash)
    if existing:
        doc = existing
        await repo.update_document(
            doc.id,
            status=ProcessingStatus.QUEUED.value,
            current_stage="QUEUED",
            error_message=None,
            error_code=None,
        )
        await db.commit()
    else:
        from app.config import get_settings
        settings = get_settings()

        doc = await repo.create_document(
            filename=result.sanitized_filename,
            original_filename=original_name,
            file_hash=result.file_hash,
            file_size_bytes=result.file_size_bytes,
            page_count=result.page_count,
            mime_type=result.mime_type,
            status=ProcessingStatus.QUEUED.value,
            pipeline_version=settings.PIPELINE_VERSION,
            extractor_version=settings.EXTRACTOR_VERSION,
            normalizer_version=settings.NORMALIZER_VERSION,
            prompt_version=settings.PROMPT_VERSION,
            model_name=settings.EXTRACTION_MODEL,
            embedding_model=settings.EMBEDDING_MODEL,
        )
        await db.commit()

    # Dispatch background task for real-time stage execution
    background_tasks.add_task(_run_pipeline_background, str(doc.id), str(file_path))

    return UploadResponse(
        document_id=str(doc.id),
        filename=result.sanitized_filename,
        status=ProcessingStatus.QUEUED.value,
        page_count=result.page_count,
        message="Document uploaded. Processing stages in real-time.",
    )



@router.get("/documents/stats/overview", response_model=DashboardStats)
@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get dashboard statistics."""
    repo = PostgresRepository(db)

    docs = await repo.list_documents()
    total_docs = len(docs)
    processing = sum(1 for d in docs if d.status not in ("COMPLETED", "FAILED", "QUEUED"))
    completed = sum(1 for d in docs if d.status == "COMPLETED")
    failed = sum(1 for d in docs if d.status == "FAILED")

    total_facts = await repo.count_facts()
    total_rels = await repo.count_relationships()
    corroborations = await repo.count_relationships("CORROBORATES")
    contradictions = await repo.count_relationships("CONTRADICTS")
    contextual = await repo.count_relationships("CONTEXTUAL_DIFFERENCE")
    superseded = await repo.count_relationships("SUPERSEDES")

    return DashboardStats(
        total_documents=total_docs,
        total_facts=total_facts,
        total_relationships=total_rels,
        corroborations=corroborations,
        contradictions=contradictions,
        contextual_differences=contextual,
        superseded_facts=superseded,
        superseded=superseded,
        documents_processing=processing,
        documents_completed=completed,
        documents_failed=failed,
    )


@router.get("/documents", response_model=PaginatedDocumentList)
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List all documents with pagination."""
    repo = PostgresRepository(db)
    docs = await repo.list_documents(limit=limit, offset=skip)
    total = await repo.count_documents()

    items = []
    for doc in docs:
        facts_count = await repo.count_facts(doc.id)
        items.append(DocumentResponse(
            id=str(doc.id),
            filename=doc.filename,
            original_filename=doc.original_filename,
            page_count=doc.page_count or 1,
            status=doc.status or "COMPLETED",
            organization=doc.organization,
            document_type=doc.document_type,
            document_title=doc.document_title,
            publication_date=doc.publication_date,
            doc_date=str(doc.publication_date) if doc.publication_date else None,
            sha256_hash=doc.file_hash,
            default_currency=doc.default_currency,
            facts_count=facts_count,
            created_at=doc.created_at,
        ))
    return PaginatedDocumentList(items=items, total=total)


@router.get("/documents/{doc_id}", response_model=DocumentDetailResponse)
async def get_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    """Get document detail with context and metadata."""
    repo = PostgresRepository(db)
    try:
        d_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document UUID")

    doc = await repo.get_document(d_uuid)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    facts_count = await repo.count_facts(doc.id)

    return DocumentDetailResponse(
        id=str(doc.id),
        filename=doc.filename,
        original_filename=doc.original_filename,
        file_hash=doc.file_hash,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count or 1,
        mime_type=doc.mime_type,
        status=doc.status or "COMPLETED",
        organization=doc.organization,
        document_type=doc.document_type,
        document_title=doc.document_title,
        publication_date=doc.publication_date,
        doc_date=str(doc.publication_date) if doc.publication_date else None,
        sha256_hash=doc.file_hash,
        reporting_period_start=doc.reporting_period_start,
        reporting_period_end=doc.reporting_period_end,
        default_currency=doc.default_currency,
        geography=doc.geography,
        language=doc.language,
        source_priority=doc.source_priority,
        current_stage=doc.current_stage,
        last_successful_stage=doc.last_successful_stage,
        retry_count=doc.retry_count,
        error_code=doc.error_code,
        error_message=doc.error_message,
        pipeline_version=doc.pipeline_version,
        extractor_version=doc.extractor_version,
        model_name=doc.model_name,
        facts_count=facts_count,
        created_at=doc.created_at,
    )


@router.get("/documents/{doc_id}/status", response_model=ProcessingStatusResponse)
async def get_processing_status(doc_id: str, db: AsyncSession = Depends(get_db)):
    """Get processing status with stage-level detail."""
    repo = PostgresRepository(db)
    try:
        d_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document UUID")

    doc = await repo.get_document(d_uuid)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    facts_count = await repo.count_facts(doc.id)

    return ProcessingStatusResponse(
        document_id=str(doc.id),
        status=doc.status or "COMPLETED",
        current_stage=doc.current_stage,
        last_successful_stage=doc.last_successful_stage,
        retry_count=doc.retry_count,
        error_code=doc.error_code,
        error_message=doc.error_message,
        facts_extracted=facts_count,
    )


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    """Delete document and all associated facts/relationships."""
    repo = PostgresRepository(db)
    try:
        d_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document UUID")

    doc = await repo.get_document(d_uuid)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    from app.storage.qdrant_repository import QdrantRepository
    try:
        qdrant = QdrantRepository()
        await qdrant.delete_by_document(str(doc.id))
    except Exception:
        pass

    await repo.delete_document(d_uuid)

    from app.config import get_settings
    settings = get_settings()
    file_path = Path(settings.UPLOAD_DIR) / doc.filename
    if file_path.exists():
        file_path.unlink()

    return {"message": "Document deleted successfully"}
