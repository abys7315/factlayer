"""Fact routes — list, search, detail with evidence."""

from __future__ import annotations

import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.models.database import get_db
from app.models.fact import Fact
from app.models.evidence import Evidence
from app.storage.postgres_repository import PostgresRepository
from app.api.schemas.responses import (
    FactResponse, FactDetailResponse, EvidenceResponse, PaginatedFactList,
)

router = APIRouter()


def _to_fact_response(f: Fact) -> FactResponse:
    return FactResponse(
        id=str(f.id),
        document_id=str(f.document_id),
        entity_name=f.subject,
        subject=f.subject,
        attribute=f.predicate,
        predicate=f.predicate,
        value_text=f.object_value,
        object_value=f.object_value,
        normalized_value=f.object_numeric if f.object_numeric is not None else f.object_value,
        object_numeric=f.object_numeric,
        unit=f.unit,
        original_text=f.original_text or f.object_value or "",
        fact_type=f.fact_type or "EXTRACTED",
        category=f.category or "General",
        fiscal_year=f.fiscal_year,
        fiscal_quarter=f.fiscal_quarter,
        validity_start=f.fiscal_year or (str(f.document_date) if f.document_date else None),
        validity_end=f.fiscal_year,
        scope=f.scope or "Consolidated",
        geography=f.geography or "Global",
        basis=f.basis or "GAAP",
        currency=f.currency or "USD",
        context_fingerprint=f.context_fingerprint or "",
        provenance_quality=f.provenance_quality or "HIGH",
        confidence=f.confidence or 0.95,
        confidence_score=f.confidence or 0.95,
        is_uncertain=bool(f.is_uncertain),
        doc_date=str(f.document_date) if f.document_date else None,
        document_date=f.document_date,
        created_at=f.created_at,
    )


@router.get("/facts", response_model=PaginatedFactList)
async def list_facts(
    document_id: str | None = Query(None),
    entity_id: str | None = Query(None),
    entity_name: str | None = Query(None),
    attribute: str | None = Query(None),
    category: str | None = Query(None),
    min_confidence: float | None = Query(None),
    skip: int = Query(0, ge=0),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List and search facts with comprehensive metadata filters."""
    actual_offset = max(skip, offset)
    query = select(Fact).where(Fact.is_canonical == True)

    if document_id:
        try:
            query = query.where(Fact.document_id == uuid.UUID(document_id))
        except ValueError:
            pass
    if entity_id:
        try:
            query = query.where(Fact.entity_id == uuid.UUID(entity_id))
        except ValueError:
            pass
    if entity_name:
        query = query.where(Fact.subject.ilike(f"%{entity_name}%"))
    if attribute:
        query = query.where(Fact.predicate.ilike(f"%{attribute}%"))
    if category:
        query = query.where(Fact.category.ilike(f"%{category}%"))
    if min_confidence is not None:
        query = query.where(Fact.confidence >= min_confidence)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_res = await db.execute(count_query)
    total = total_res.scalar_one() or 0

    # Paginate
    query = query.order_by(Fact.created_at.desc()).offset(actual_offset).limit(limit)
    result = await db.execute(query)
    facts = result.scalars().all()

    items = [_to_fact_response(f) for f in facts]
    return PaginatedFactList(items=items, total=total)


@router.get("/facts/{fact_id}", response_model=FactDetailResponse)
async def get_fact(fact_id: str, db: AsyncSession = Depends(get_db)):
    """Get fact detail with all evidence bounding boxes."""
    repo = PostgresRepository(db)
    try:
        f_uuid = uuid.UUID(fact_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid fact UUID")

    fact = await repo.get_fact(f_uuid)
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")

    evidence = await repo.get_evidence_for_fact(fact.id)

    base = _to_fact_response(fact)
    return FactDetailResponse(
        **base.model_dump(),
        reporting_period_label=fact.reporting_period_label,
        valid_from=fact.valid_from,
        valid_to=fact.valid_to,
        is_canonical=fact.is_canonical,
        extractor_version=fact.extractor_version or "v1.0.0",
        prompt_version=fact.prompt_version or "2026-09-07",
        model_name=fact.model_name or "gemini-2.5-flash",
        evidence=[
            EvidenceResponse(
                id=str(e.id),
                evidence_id=str(e.id),
                evidence_type=e.evidence_type,
                source_type=e.source_type,
                block_type=e.source_type or "text",
                excerpt=e.excerpt,
                snippet=e.excerpt,
                page_number=e.page_number or 1,
                bbox_x0=e.bbox_x0,
                bbox_y0=e.bbox_y0,
                bbox_x1=e.bbox_x1,
                bbox_y1=e.bbox_y1,
                bbox={
                    "x0": (e.bbox_x0 / e.page_width) if e.bbox_x0 and e.page_width else 0.1,
                    "y0": (e.bbox_y0 / e.page_height) if e.bbox_y0 and e.page_height else 0.1,
                    "x1": (e.bbox_x1 / e.page_width) if e.bbox_x1 and e.page_width else 0.9,
                    "y1": (e.bbox_y1 / e.page_height) if e.bbox_y1 and e.page_height else 0.2,
                },
                is_validated=e.is_validated,
                validation_method=e.validation_method,
                validation_score=e.validation_score,
            )
            for e in evidence
        ],
    )


@router.get("/facts/{fact_id}/evidence")
async def get_fact_evidence(fact_id: str, db: AsyncSession = Depends(get_db)):
    """Get all evidence for a fact."""
    repo = PostgresRepository(db)
    try:
        f_uuid = uuid.UUID(fact_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid fact UUID")

    evidence = await repo.get_evidence_for_fact(f_uuid)
    items = [
        EvidenceResponse(
            id=str(e.id),
            evidence_id=str(e.id),
            evidence_type=e.evidence_type,
            source_type=e.source_type,
            block_type=e.source_type or "text",
            excerpt=e.excerpt,
            snippet=e.excerpt,
            page_number=e.page_number or 1,
            bbox_x0=e.bbox_x0,
            bbox_y0=e.bbox_y0,
            bbox_x1=e.bbox_x1,
            bbox_y1=e.bbox_y1,
            bbox={
                "x0": (e.bbox_x0 / e.page_width) if e.bbox_x0 and e.page_width else 0.1,
                "y0": (e.bbox_y0 / e.page_height) if e.bbox_y0 and e.page_height else 0.1,
                "x1": (e.bbox_x1 / e.page_width) if e.bbox_x1 and e.page_width else 0.9,
                "y1": (e.bbox_y1 / e.page_height) if e.bbox_y1 and e.page_height else 0.2,
            },
            is_validated=e.is_validated,
            validation_method=e.validation_method,
            validation_score=e.validation_score,
        )
        for e in evidence
    ]
    return {"items": items, "total": len(items)}
