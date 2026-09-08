"""Relationship routes — list, detail, filter by type (Contradiction, Supersession, etc.)."""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.models.database import get_db
from app.models.document import Document
from app.models.fact import Fact
from app.models.relationship import FactRelationship
from app.storage.postgres_repository import PostgresRepository
from app.api.schemas.responses import (
    RelationshipResponse, RelationshipDetailResponse,
    FactResponse, EvidenceResponse, PaginatedRelationshipList,
)

router = APIRouter()


def _to_fact_response(f: Fact | None, doc: Document | None = None) -> FactResponse | None:
    if not f:
        return None
    doc_filename = doc.original_filename if doc else None
    doc_title = (doc.document_title or doc.original_filename) if doc else None
    return FactResponse(
        id=str(f.id),
        document_id=str(f.document_id),
        document_filename=doc_filename,
        document_title=doc_title,
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


def _to_evidence_response(e, doc: Document | None = None) -> EvidenceResponse:
    pw = e.page_width if (e.page_width and e.page_width > 0) else 612.0
    ph = e.page_height if (e.page_height and e.page_height > 0) else 792.0
    doc_id = str(e.document_id) if getattr(e, "document_id", None) else (str(doc.id) if doc else None)
    doc_name = (doc.document_title or doc.original_filename) if doc else None
    return EvidenceResponse(
        id=str(e.id),
        evidence_id=str(e.id),
        document_id=doc_id,
        document_name=doc_name,
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

    doc_ids = {f.document_id for f in fact_map.values() if f.document_id}
    doc_map: dict[uuid.UUID, Document] = {}
    if doc_ids:
        docs_res = await db.execute(select(Document).where(Document.id.in_(list(doc_ids))))
        for d in docs_res.scalars().all():
            doc_map[d.id] = d

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

        engine_name = r.classification_method or "comparison_engine"
        if engine_name == "deterministic":
            engine_name = "comparison_engine"

        doc_a = doc_map.get(fa.document_id) if (fa and fa.document_id) else None
        doc_b = doc_map.get(fb.document_id) if (fb and fb.document_id) else None

        items.append(
            RelationshipResponse(
                id=str(r.id),
                fact_a_id=str(r.fact_a_id),
                fact_b_id=str(r.fact_b_id),
                relationship_type=r.relationship_type,
                confidence=r.confidence or 0.9,
                confidence_score=r.confidence or 0.9,
                engine=engine_name,
                classification_method=r.classification_method or "deterministic",
                explanation=r.explanation or "",
                context_difference_type=r.context_difference_type,
                supersession_date=r.supersession_date,
                reasoning_trace=r.reasoning_trace,
                fact_a=_to_fact_response(fa, doc_a),
                fact_b=_to_fact_response(fb, doc_b),
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


@router.get("/relationships/corroborations", response_model=PaginatedRelationshipList)
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

    doc_a = await repo.get_document(fact_a.document_id) if (fact_a and fact_a.document_id) else None
    doc_b = await repo.get_document(fact_b.document_id) if (fact_b and fact_b.document_id) else None

    evidence_a = await repo.get_evidence_for_fact(rel.fact_a_id) if rel.fact_a_id else []
    evidence_b = await repo.get_evidence_for_fact(rel.fact_b_id) if rel.fact_b_id else []

    engine_name = rel.classification_method or "comparison_engine"
    if engine_name == "deterministic":
        engine_name = "comparison_engine"

    return RelationshipDetailResponse(
        id=str(rel.id),
        fact_a_id=str(rel.fact_a_id),
        fact_b_id=str(rel.fact_b_id),
        relationship_type=rel.relationship_type,
        confidence=rel.confidence or 0.9,
        confidence_score=rel.confidence or 0.9,
        engine=engine_name,
        classification_method=rel.classification_method or "deterministic",
        explanation=rel.explanation or "",
        context_difference_type=rel.context_difference_type,
        supersession_date=rel.supersession_date,
        reasoning_trace=rel.reasoning_trace,
        created_at=rel.created_at,
        fact_a=_to_fact_response(fact_a, doc_a),
        fact_b=_to_fact_response(fact_b, doc_b),
        evidence_a=[_to_evidence_response(e, doc_a) for e in evidence_a],
        evidence_b=[_to_evidence_response(e, doc_b) for e in evidence_b],
        classifier_version=rel.classifier_version or "v1.0.0",
        model_name=getattr(rel, "llm_model", None) or ("gemini-2.5-pro" if "llm" in engine_name else "deterministic_rules"),
    )


async def _run_recompute_job():
    """Background execution of cross-document candidate reasoning with real-time commits."""
    from collections import defaultdict
    from app.models.database import get_session_factory
    from app.models.document import Document
    from app.models.fact import Fact
    from app.models.entity import Entity
    from app.normalization.entity_resolver import EntityResolver
    from app.reasoning.comparison_engine import ComparisonEngine

    session_factory = get_session_factory()
    resolver = EntityResolver()
    engine = ComparisonEngine()

    async with session_factory() as session:
        repo = PostgresRepository(session)
        # 1. Fetch documents for context
        docs_res = await session.execute(select(Document))
        docs = {d.id: d for d in docs_res.scalars().all()}

        # 2. Fetch canonical facts
        facts_res = await session.execute(
            select(Fact).where(Fact.is_canonical == True).order_by(Fact.created_at)
        )
        facts = facts_res.scalars().all()

        # 3. Ensure entity resolution
        entity_cache = {}
        for f in facts:
            doc = docs.get(f.document_id)
            org = doc.organization if doc else None
            geography = doc.geography if doc else None

            res = resolver.resolve(f.subject, context={"organization": org, "geography": geography})
            canonical = res.canonical_name or f.subject

            if canonical in entity_cache:
                ent = entity_cache[canonical]
            else:
                ent = await repo.get_entity_by_name(canonical)
                if not ent:
                    ent = await repo.find_entity_by_alias(f.subject)
                if not ent:
                    ent = await repo.create_entity(
                        canonical_name=canonical,
                        entity_type="ORG",
                        description=f"Entity {canonical}",
                    )
                entity_cache[canonical] = ent

            if f.entity_id != ent.id:
                f.entity_id = ent.id

        await session.commit()

        # 4. Group candidate facts by canonical predicate & entity
        grouped_candidates = defaultdict(list)
        for f in facts:
            canon_pred = engine.predicate_resolver.canonicalize(f.predicate)
            grouped_candidates[(canon_pred, f.entity_id)].append(f)

        # 5. Compare candidate pairs
        new_relationships = 0
        for (canon_pred, entity_id), bucket in grouped_candidates.items():
            if len(bucket) < 2:
                continue
            sub_bucket = bucket[:40]
            for i in range(len(sub_bucket)):
                fa = sub_bucket[i]
                for j in range(i + 1, len(sub_bucket)):
                    fb = sub_bucket[j]
                    if fa.id == fb.id:
                        continue
                    if fa.document_id == fb.document_id and fa.object_value == fb.object_value and fa.original_text == fb.original_text:
                        continue
                    if await repo.relationship_exists(fa.id, fb.id):
                        continue

                    res = engine.compare(fa, fb)
                    if res.relationship_type == "UNRELATED":
                        continue

                    ev_a = await repo.get_evidence_for_fact(fa.id)
                    ev_b = await repo.get_evidence_for_fact(fb.id)

                    await repo.create_relationship(
                        fact_a_id=fa.id,
                        fact_b_id=fb.id,
                        relationship_type=res.relationship_type,
                        confidence=res.confidence,
                        classification_method=res.classification_method,
                        reasoning_trace=res.reasoning_trace,
                        explanation=res.explanation,
                        context_difference_type=res.context_difference_type,
                        supersession_date=res.supersession_date,
                        supporting_evidence_a=[str(e.id) for e in ev_a],
                        supporting_evidence_b=[str(e.id) for e in ev_b],
                        classifier_version="v2.0.0",
                    )
                    new_relationships += 1

                    # Commit periodically to trigger real-time SSE updates
                    if new_relationships % 10 == 0:
                        await session.commit()

        await session.commit()


@router.post("/relationships/recompute")
async def recompute_relationships(
    background_tasks: BackgroundTasks,
    wait: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger real-time cross-document relationship reasoning across all canonical facts.
    Dispatches in background with incremental commits so SSE streams live updates.
    """
    if wait:
        await _run_recompute_job()
        repo = PostgresRepository(db)
        total_rels = await repo.count_relationships()
        corroborations = await repo.count_relationships("CORROBORATES")
        contradictions = await repo.count_relationships("CONTRADICTS")
        return {
            "status": "completed",
            "total_relationships": total_rels,
            "total_contradictions": contradictions,
            "total_corroborations": corroborations,
        }

    background_tasks.add_task(_run_recompute_job)
    return {
        "status": "started",
        "message": "Real-time cross-document reasoning audit started in the background. Updates will stream via SSE.",
    }

