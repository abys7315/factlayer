"""Relationship routes — list, detail, filter by type (Contradiction, Supersession, etc.)."""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.models.database import get_db
from app.models.fact import Fact
from app.models.relationship import FactRelationship
from app.storage.postgres_repository import PostgresRepository
from app.api.schemas.responses import (
    RelationshipResponse, RelationshipDetailResponse,
    FactResponse, EvidenceResponse, PaginatedRelationshipList,
)

router = APIRouter()


def _to_fact_response(f: Fact | None) -> FactResponse | None:
    if not f:
        return None
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


def _to_evidence_response(e) -> EvidenceResponse:
    pw = e.page_width if (e.page_width and e.page_width > 0) else 612.0
    ph = e.page_height if (e.page_height and e.page_height > 0) else 792.0
    return EvidenceResponse(
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
            "x0": (e.bbox_x0 / pw) if e.bbox_x0 is not None else 0.1,
            "y0": (e.bbox_y0 / ph) if e.bbox_y0 is not None else 0.1,
            "x1": (e.bbox_x1 / pw) if e.bbox_x1 is not None else 0.9,
            "y1": (e.bbox_y1 / ph) if e.bbox_y1 is not None else 0.2,
        },
        is_validated=e.is_validated,
        validation_method=e.validation_method,
        validation_score=e.validation_score,
    )


async def _fetch_paginated_relationships(
    db: AsyncSession,
    rel_type: str | None = None,
    document_id: str | None = None,
    fact_id: str | None = None,
    min_confidence: float | None = None,
    skip: int = 0,
    offset: int = 0,
    limit: int = 100,
) -> PaginatedRelationshipList:
    actual_offset = max(skip, offset)
    query = select(FactRelationship)

    if rel_type:
        query = query.where(FactRelationship.relationship_type == rel_type)
    if min_confidence is not None:
        query = query.where(FactRelationship.confidence >= min_confidence)
    if fact_id:
        try:
            f_uuid = uuid.UUID(fact_id)
            query = query.where(or_(
                FactRelationship.fact_a_id == f_uuid,
                FactRelationship.fact_b_id == f_uuid,
            ))
        except ValueError:
            pass

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_res = await db.execute(count_query)
    total = total_res.scalar_one() or 0

    # Paginate
    query = query.order_by(FactRelationship.created_at.desc()).offset(actual_offset).limit(limit)
    result = await db.execute(query)
    rels = result.scalars().all()

    # Collect fact IDs to fetch in bulk
    fact_ids = set()
    for r in rels:
        if r.fact_a_id:
            fact_ids.add(r.fact_a_id)
        if r.fact_b_id:
            fact_ids.add(r.fact_b_id)

    fact_map: dict[uuid.UUID, Fact] = {}
    if fact_ids:
        facts_res = await db.execute(select(Fact).where(Fact.id.in_(list(fact_ids))))
        for f in facts_res.scalars().all():
            fact_map[f.id] = f

    items = []
    for r in rels:
        fa = fact_map.get(r.fact_a_id)
        fb = fact_map.get(r.fact_b_id)

        # If filtering by document_id, check if either fact belongs to doc
        if document_id:
            try:
                doc_uuid = uuid.UUID(document_id)
                if not ((fa and fa.document_id == doc_uuid) or (fb and fb.document_id == doc_uuid)):
                    continue
            except ValueError:
                pass

        items.append(
            RelationshipResponse(
                id=str(r.id),
                fact_a_id=str(r.fact_a_id),
                fact_b_id=str(r.fact_b_id),
                relationship_type=r.relationship_type,
                confidence=r.confidence or 0.9,
                confidence_score=r.confidence or 0.9,
                engine="llm_reasoner",
                classification_method=r.classification_method or "deterministic",
                explanation=r.explanation or "",
                context_difference_type=r.context_difference_type,
                supersession_date=r.supersession_date,
                reasoning_trace=r.reasoning_trace,
                fact_a=_to_fact_response(fa),
                fact_b=_to_fact_response(fb),
                created_at=r.created_at,
            )
        )

    return PaginatedRelationshipList(items=items, total=total)


@router.get("/relationships", response_model=PaginatedRelationshipList)
async def list_relationships(
    type: str | None = Query(None, description="Filter by relationship type"),
    document_id: str | None = Query(None),
    fact_id: str | None = Query(None),
    min_confidence: float | None = Query(None),
    skip: int = Query(0, ge=0),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List cross-document relationships with eager-loaded facts and filters."""
    return await _fetch_paginated_relationships(
        db=db,
        rel_type=type,
        document_id=document_id,
        fact_id=fact_id,
        min_confidence=min_confidence,
        skip=skip,
        offset=offset,
        limit=limit,
    )


@router.get("/relationships/contradictions", response_model=PaginatedRelationshipList)
@router.get("/relationships/type/contradictions", response_model=PaginatedRelationshipList)
async def get_contradictions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get all contradictory factual statements across documents."""
    return await _fetch_paginated_relationships(db=db, rel_type="CONTRADICTS", skip=skip, limit=limit)


@router.get("/relationships/supersedes", response_model=PaginatedRelationshipList)
@router.get("/relationships/type/superseded", response_model=PaginatedRelationshipList)
async def get_superseded(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get all temporally superseded facts."""
    return await _fetch_paginated_relationships(db=db, rel_type="SUPERSEDES", skip=skip, limit=limit)


@router.get("/relationships/type/corroborations", response_model=PaginatedRelationshipList)
async def get_corroborations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get all corroborated factual statements across documents."""
    return await _fetch_paginated_relationships(db=db, rel_type="CORROBORATES", skip=skip, limit=limit)


@router.get("/relationships/type/contextual", response_model=PaginatedRelationshipList)
async def get_contextual(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get all contextual differences (GAAP vs non-GAAP, regional scopes)."""
    return await _fetch_paginated_relationships(db=db, rel_type="CONTEXTUAL_DIFFERENCE", skip=skip, limit=limit)


@router.get("/relationships/{rel_id}", response_model=RelationshipDetailResponse)
async def get_relationship(rel_id: str, db: AsyncSession = Depends(get_db)):
    """Get relationship detail with both facts and bounding-box evidence."""
    repo = PostgresRepository(db)
    try:
        r_uuid = uuid.UUID(rel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid relationship UUID")

    rel = await repo.get_relationship(r_uuid)
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")

    fact_a = await repo.get_fact(rel.fact_a_id) if rel.fact_a_id else None
    fact_b = await repo.get_fact(rel.fact_b_id) if rel.fact_b_id else None

    evidence_a = await repo.get_evidence_for_fact(rel.fact_a_id) if rel.fact_a_id else []
    evidence_b = await repo.get_evidence_for_fact(rel.fact_b_id) if rel.fact_b_id else []

    return RelationshipDetailResponse(
        id=str(rel.id),
        fact_a_id=str(rel.fact_a_id),
        fact_b_id=str(rel.fact_b_id),
        relationship_type=rel.relationship_type,
        confidence=rel.confidence or 0.9,
        confidence_score=rel.confidence or 0.9,
        engine="llm_reasoner",
        classification_method=rel.classification_method or "deterministic",
        explanation=rel.explanation or "",
        context_difference_type=rel.context_difference_type,
        supersession_date=rel.supersession_date,
        reasoning_trace=rel.reasoning_trace,
        created_at=rel.created_at,
        fact_a=_to_fact_response(fact_a),
        fact_b=_to_fact_response(fact_b),
        evidence_a=[_to_evidence_response(e) for e in evidence_a],
        evidence_b=[_to_evidence_response(e) for e in evidence_b],
        classifier_version=rel.classifier_version or "v1.0.0",
        model_name=rel.model_name or "gemini-2.5-pro",
    )
