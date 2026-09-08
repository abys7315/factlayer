"""Knowledge Graph routes — subgraphs, multi-hop entity-fact-document topologies, and graph discovery."""

from __future__ import annotations

import uuid
from typing import Any
from collections import defaultdict
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, desc

from app.models.database import get_db
from app.models.document import Document
from app.models.fact import Fact
from app.models.entity import Entity
from app.models.evidence import Evidence
from app.models.relationship import FactRelationship

router = APIRouter()


@router.get("/graph")
async def get_knowledge_graph(
    relationship_id: str | None = Query(None, description="Focus relationship UUID"),
    fact_id: str | None = Query(None, description="Focus fact UUID"),
    entity_name: str | None = Query(None, description="Focus entity or subject name"),
    document_id: str | None = Query(None, description="Filter by document UUID"),
    doc_id: str | None = Query(None, description="Filter by document UUID (alias)"),
    relationship_type: str | None = Query(None, description="Filter by relationship type (CONTRADICTS, SUPERSEDES, etc.)"),
    preset: str | None = Query(None, description="Preset filter: contradictions, corroborations, supersedes, relationships, contextual, all"),
    limit: int = Query(80, ge=10, le=250, description="Max fact nodes to return"),
    db: AsyncSession = Depends(get_db),
):
    """
    Build a multi-hop visual knowledge subgraph connecting:
    - Entity nodes (Subject / Organization)
    - Fact Claim nodes (with values, metrics, confidence, provenance)
    - Document nodes (Source PDFs)
    - Relationship edges (CONTRADICTS, SUPERSEDES, CORROBORATES, CONTEXTUAL_DIFFERENCE)
    - Provenance & Subject edges (HAS_FACT, EXTRACTED_FROM)
    """
    selected_fact_ids: set[uuid.UUID] = set()
    selected_relationships: list[FactRelationship] = []
    focused_id: str | None = None

    # Safe normalization of input parameters
    target_rel_id = str(relationship_id).strip() if (relationship_id and isinstance(relationship_id, str) and str(relationship_id).strip() and not str(relationship_id).startswith("Query")) else None
    target_fact_id = str(fact_id).strip() if (fact_id and isinstance(fact_id, str) and str(fact_id).strip() and not str(fact_id).startswith("Query")) else None
    raw_doc = document_id or doc_id
    target_doc_id = str(raw_doc).strip() if (raw_doc and isinstance(raw_doc, str) and str(raw_doc).strip() and not str(raw_doc).startswith("Query")) else None
    target_entity = str(entity_name).strip() if (entity_name and isinstance(entity_name, str) and str(entity_name).strip() and not str(entity_name).startswith("Query")) else None
    target_preset = str(preset).strip().lower() if (preset and isinstance(preset, str) and str(preset).strip() and not str(preset).startswith("Query")) else None
    target_rel_type = str(relationship_type).strip().upper() if (relationship_type and isinstance(relationship_type, str) and str(relationship_type).strip() and not str(relationship_type).startswith("Query")) else None

    try:
        target_limit = int(limit) if (limit and not str(limit).startswith("Query")) else 80
    except (ValueError, TypeError):
        target_limit = 80

    focused_entity: str | None = target_entity
    filter_scope: str = "all"

    # PRIORITY 1: Specific Relationship Focus
    if target_rel_id:
        try:
            rel_uuid = uuid.UUID(target_rel_id)
            rel_res = await db.execute(select(FactRelationship).where(FactRelationship.id == rel_uuid))
            target_rel = rel_res.scalar_one_or_none()
            if target_rel:
                filter_scope = f"relationship:{target_rel.relationship_type}"
                selected_relationships.append(target_rel)
                if target_rel.fact_a_id:
                    selected_fact_ids.add(target_rel.fact_a_id)
                    focused_id = str(target_rel.fact_a_id)
                if target_rel.fact_b_id:
                    selected_fact_ids.add(target_rel.fact_b_id)

                # Fetch other facts for these entities to give context
                if selected_fact_ids:
                    ref_facts = (await db.execute(select(Fact).where(Fact.id.in_(list(selected_fact_ids))))).scalars().all()
                    subjects = {f.subject for f in ref_facts if f.subject}
                    if subjects:
                        siblings_res = await db.execute(
                            select(Fact).where(Fact.subject.in_(list(subjects))).limit(25)
                        )
                        for sib in siblings_res.scalars().all():
                            selected_fact_ids.add(sib.id)

                # Fetch other relationships among these facts
                if len(selected_fact_ids) > 1:
                    extra_rels_res = await db.execute(
                        select(FactRelationship).where(
                            and_(
                                FactRelationship.fact_a_id.in_(list(selected_fact_ids)),
                                FactRelationship.fact_b_id.in_(list(selected_fact_ids)),
                            )
                        ).limit(30)
                    )
                    existing_rel_ids = {r.id for r in selected_relationships}
                    for r in extra_rels_res.scalars().all():
                        if r.id not in existing_rel_ids:
                            selected_relationships.append(r)
                            existing_rel_ids.add(r.id)
        except ValueError:
            pass

    # PRIORITY 2: Specific Fact Claim Focus
    elif target_fact_id:
        try:
            target_uuid = uuid.UUID(target_fact_id)
            target_fact_res = await db.execute(select(Fact).where(Fact.id == target_uuid))
            target_fact = target_fact_res.scalar_one_or_none()
            if target_fact:
                filter_scope = f"fact:{target_fact.predicate}"
                focused_id = str(target_fact.id)
                focused_entity = target_fact.subject
                selected_fact_ids.add(target_fact.id)

                # Fetch all relationships involving this fact
                direct_rels_res = await db.execute(
                    select(FactRelationship).where(
                        or_(
                            FactRelationship.fact_a_id == target_uuid,
                            FactRelationship.fact_b_id == target_uuid,
                        )
                    ).limit(40)
                )
                direct_rels = list(direct_rels_res.scalars().all())
                selected_relationships.extend(direct_rels)
                for r in direct_rels:
                    if r.fact_a_id:
                        selected_fact_ids.add(r.fact_a_id)
                    if r.fact_b_id:
                        selected_fact_ids.add(r.fact_b_id)

                # Also pull sibling facts for the same entity/subject or same document
                siblings_res = await db.execute(
                    select(Fact).where(
                        or_(
                            Fact.subject == target_fact.subject,
                            and_(Fact.document_id == target_fact.document_id, Fact.id != target_fact.id),
                        )
                    ).limit(25)
                )
                siblings = siblings_res.scalars().all()
                for sib in siblings:
                    selected_fact_ids.add(sib.id)

                # Find any relationships between all collected facts
                if len(selected_fact_ids) > 1:
                    extra_rels_res = await db.execute(
                        select(FactRelationship).where(
                            and_(
                                FactRelationship.fact_a_id.in_(list(selected_fact_ids)),
                                FactRelationship.fact_b_id.in_(list(selected_fact_ids)),
                            )
                        ).limit(30)
                    )
                    existing_rel_ids = {r.id for r in selected_relationships}
                    for r in extra_rels_res.scalars().all():
                        if r.id not in existing_rel_ids:
                            selected_relationships.append(r)
                            existing_rel_ids.add(r.id)
        except ValueError:
            pass

    # PRIORITY 3: Document Focus
    elif target_doc_id:
        try:
            doc_uuid = uuid.UUID(target_doc_id)
            doc_q = select(Fact).where(Fact.document_id == doc_uuid)
            facts_res = await db.execute(doc_q.limit(target_limit))
            doc_facts = facts_res.scalars().all()
            filter_scope = f"document:{target_doc_id}"
            for f in doc_facts:
                selected_fact_ids.add(f.id)

            if selected_fact_ids:
                rel_q = select(FactRelationship).where(
                    or_(
                        FactRelationship.fact_a_id.in_(list(selected_fact_ids)),
                        FactRelationship.fact_b_id.in_(list(selected_fact_ids)),
                    )
                )
                if target_rel_type:
                    rel_q = rel_q.where(FactRelationship.relationship_type == target_rel_type)
                rels_res = await db.execute(rel_q.limit(50))
                selected_relationships = list(rels_res.scalars().all())
                for r in selected_relationships:
                    if r.fact_a_id:
                        selected_fact_ids.add(r.fact_a_id)
                    if r.fact_b_id:
                        selected_fact_ids.add(r.fact_b_id)
        except ValueError:
            pass

    # PRIORITY 4: Entity Focus
    elif target_entity:
        filter_scope = f"entity:{target_entity}"
        facts_res = await db.execute(
            select(Fact).where(Fact.subject.ilike(f"%{target_entity}%")).limit(target_limit)
        )
        entity_facts = facts_res.scalars().all()
        for f in entity_facts:
            selected_fact_ids.add(f.id)

        if selected_fact_ids:
            rel_q = select(FactRelationship).where(
                or_(
                    FactRelationship.fact_a_id.in_(list(selected_fact_ids)),
                    FactRelationship.fact_b_id.in_(list(selected_fact_ids)),
                )
            )
            if target_rel_type:
                rel_q = rel_q.where(FactRelationship.relationship_type == target_rel_type)
            rels_res = await db.execute(rel_q.limit(50))
            selected_relationships = list(rels_res.scalars().all())
            for r in selected_relationships:
                if r.fact_a_id:
                    selected_fact_ids.add(r.fact_a_id)
                if r.fact_b_id:
                    selected_fact_ids.add(r.fact_b_id)

    # PRIORITY 5: Relationship Types & Presets
    elif target_preset == "contradictions" or target_rel_type == "CONTRADICTS":
        filter_scope = "preset:contradictions"
        rel_q = (
            select(FactRelationship)
            .where(FactRelationship.relationship_type == "CONTRADICTS")
            .order_by(desc(FactRelationship.created_at), desc(FactRelationship.confidence))
            .limit(target_limit)
        )
        rel_res = await db.execute(rel_q)
        selected_relationships = list(rel_res.scalars().all())
        for r in selected_relationships:
            if r.fact_a_id:
                selected_fact_ids.add(r.fact_a_id)
            if r.fact_b_id:
                selected_fact_ids.add(r.fact_b_id)

    elif target_preset == "supersedes" or target_rel_type == "SUPERSEDES":
        filter_scope = "preset:supersedes"
        rel_q = (
            select(FactRelationship)
            .where(FactRelationship.relationship_type == "SUPERSEDES")
            .order_by(desc(FactRelationship.created_at), desc(FactRelationship.confidence))
            .limit(target_limit)
        )
        rel_res = await db.execute(rel_q)
        selected_relationships = list(rel_res.scalars().all())
        for r in selected_relationships:
            if r.fact_a_id:
                selected_fact_ids.add(r.fact_a_id)
            if r.fact_b_id:
                selected_fact_ids.add(r.fact_b_id)

    elif target_preset == "corroborations" or target_rel_type == "CORROBORATES":
        filter_scope = "preset:corroborations"
        rel_q = (
            select(FactRelationship)
            .where(FactRelationship.relationship_type == "CORROBORATES")
            .order_by(desc(FactRelationship.confidence), desc(FactRelationship.created_at))
            .limit(target_limit)
        )
        rel_res = await db.execute(rel_q)
        selected_relationships = list(rel_res.scalars().all())
        for r in selected_relationships:
            if r.fact_a_id:
                selected_fact_ids.add(r.fact_a_id)
            if r.fact_b_id:
                selected_fact_ids.add(r.fact_b_id)

    elif target_preset == "contextual" or target_rel_type == "CONTEXTUAL_DIFFERENCE":
        filter_scope = "preset:contextual"
        rel_q = (
            select(FactRelationship)
            .where(FactRelationship.relationship_type == "CONTEXTUAL_DIFFERENCE")
            .order_by(desc(FactRelationship.created_at), desc(FactRelationship.confidence))
            .limit(target_limit)
        )
        rel_res = await db.execute(rel_q)
        selected_relationships = list(rel_res.scalars().all())
        for r in selected_relationships:
            if r.fact_a_id:
                selected_fact_ids.add(r.fact_a_id)
            if r.fact_b_id:
                selected_fact_ids.add(r.fact_b_id)

    elif target_preset == "relationships":
        filter_scope = "preset:relationships"
        if target_rel_type:
            rel_q = (
                select(FactRelationship)
                .where(FactRelationship.relationship_type == target_rel_type)
                .order_by(desc(FactRelationship.created_at), desc(FactRelationship.confidence))
                .limit(target_limit)
            )
            rel_res = await db.execute(rel_q)
            selected_relationships = list(rel_res.scalars().all())
        else:
            diverse_rels = []
            for rtype in ["CONTRADICTS", "SUPERSEDES", "CORROBORATES", "CONTEXTUAL_DIFFERENCE"]:
                sub_res = await db.execute(
                    select(FactRelationship)
                    .where(FactRelationship.relationship_type == rtype)
                    .order_by(desc(FactRelationship.confidence), desc(FactRelationship.created_at))
                    .limit(15)
                )
                diverse_rels.extend(sub_res.scalars().all())
            selected_relationships = diverse_rels

        for r in selected_relationships:
            if r.fact_a_id:
                selected_fact_ids.add(r.fact_a_id)
            if r.fact_b_id:
                selected_fact_ids.add(r.fact_b_id)

    # Default / Overview: load balanced cross-section across all 4 relationship types
    if not selected_fact_ids:
        filter_scope = "overview:diverse"
        diverse_rels = []
        for rtype in ["CONTRADICTS", "SUPERSEDES", "CORROBORATES", "CONTEXTUAL_DIFFERENCE"]:
            sub_res = await db.execute(
                select(FactRelationship)
                .where(FactRelationship.relationship_type == rtype)
                .order_by(desc(FactRelationship.confidence), desc(FactRelationship.created_at))
                .limit(12)
            )
            diverse_rels.extend(sub_res.scalars().all())
        selected_relationships = diverse_rels
        for r in selected_relationships:
            if r.fact_a_id:
                selected_fact_ids.add(r.fact_a_id)
            if r.fact_b_id:
                selected_fact_ids.add(r.fact_b_id)

        # Fallback if no relationships exist: load recent facts
        if not selected_fact_ids:
            recent_facts = (await db.execute(select(Fact).limit(30))).scalars().all()
            for f in recent_facts:
                selected_fact_ids.add(f.id)

    # 1. Fetch all selected facts
    all_facts: list[Fact] = []
    if selected_fact_ids:
        facts_res = await db.execute(
            select(Fact).where(Fact.id.in_(list(selected_fact_ids)))
        )
        all_facts = list(facts_res.scalars().all())

    fact_map = {f.id: f for f in all_facts}
    # Ensure selected_relationships ONLY contains relationships where BOTH facts exist
    selected_relationships = [r for r in selected_relationships if r.fact_a_id in fact_map and r.fact_b_id in fact_map]

    # 2. Fetch Evidence for all selected facts
    evidence_map: dict[uuid.UUID, Evidence] = {}
    if selected_fact_ids:
        ev_res = await db.execute(
            select(Evidence).where(Evidence.fact_id.in_(list(selected_fact_ids)))
        )
        for ev in ev_res.scalars().all():
            if ev.fact_id not in evidence_map:
                evidence_map[ev.fact_id] = ev

    # 3. Fetch all Documents involved
    doc_ids = {f.document_id for f in all_facts if f.document_id}
    doc_map: dict[uuid.UUID, Document] = {}
    if doc_ids:
        docs_res = await db.execute(
            select(Document).where(Document.id.in_(list(doc_ids)))
        )
        doc_map = {d.id: d for d in docs_res.scalars().all()}

    # Ensure targeted document is included even if it has no facts yet
    if target_doc_id:
        try:
            doc_uuid = uuid.UUID(target_doc_id)
            if doc_uuid not in doc_map:
                target_doc_res = await db.execute(select(Document).where(Document.id == doc_uuid))
                td = target_doc_res.scalar_one_or_none()
                if td:
                    doc_map[td.id] = td
        except Exception:
            pass

    # 4. Count stats per entity and relationship breakdown
    entity_facts_count: dict[str, int] = defaultdict(int)
    entity_contra_count: dict[str, int] = defaultdict(int)
    entity_corrob_count: dict[str, int] = defaultdict(int)

    for f in all_facts:
        entity_facts_count[f.subject] += 1

    stats = {
        "contradictions": 0,
        "corroborations": 0,
        "supersessions": 0,
        "contextual_differences": 0,
        "total_relationships": len(selected_relationships),
    }

    for r in selected_relationships:
        rtype = r.relationship_type or "UNRELATED"
        if rtype == "CONTRADICTS":
            stats["contradictions"] += 1
            fa = fact_map.get(r.fact_a_id)
            fb = fact_map.get(r.fact_b_id)
            if fa:
                entity_contra_count[fa.subject] += 1
            if fb:
                entity_contra_count[fb.subject] += 1
        elif rtype == "CORROBORATES":
            stats["corroborations"] += 1
            fa = fact_map.get(r.fact_a_id)
            fb = fact_map.get(r.fact_b_id)
            if fa:
                entity_corrob_count[fa.subject] += 1
            if fb:
                entity_corrob_count[fb.subject] += 1
        elif rtype == "SUPERSEDES":
            stats["supersessions"] += 1
        elif rtype == "CONTEXTUAL_DIFFERENCE":
            stats["contextual_differences"] += 1

    # 5. Construct Nodes
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    # A. Entity Hub Nodes
    entities_present = set(f.subject for f in all_facts)
    for ent_name in entities_present:
        nodes.append({
            "id": f"entity-{ent_name}",
            "type": "entity",
            "label": ent_name,
            "entity_name": ent_name,
            "fact_count": entity_facts_count[ent_name],
            "contradiction_count": entity_contra_count[ent_name],
            "corroboration_count": entity_corrob_count[ent_name],
            "is_focused": bool(focused_entity and focused_entity.lower() in ent_name.lower()),
        })

    # B. Document Nodes
    for d_id, doc in doc_map.items():
        nodes.append({
            "id": f"doc-{d_id}",
            "type": "document",
            "label": doc.document_title or doc.original_filename,
            "document_id": str(d_id),
            "filename": doc.original_filename,
            "page_count": doc.page_count or 1,
            "upload_date": str(doc.created_at) if doc.created_at else None,
            "facts_count": len([f for f in all_facts if f.document_id == d_id]),
        })

    # C. Fact Claim Nodes
    for f in all_facts:
        ev = evidence_map.get(f.id)
        doc = doc_map.get(f.document_id)
        pw = ev.page_width if (ev and ev.page_width and ev.page_width > 0) else 612.0
        ph = ev.page_height if (ev and ev.page_height and ev.page_height > 0) else 792.0

        bbox = None
        if ev and ev.bbox_x0 is not None:
            bbox = {
                "x0": ev.bbox_x0 / pw if pw > 0 else 0.1,
                "y0": ev.bbox_y0 / ph if ph > 0 else 0.1,
                "x1": ev.bbox_x1 / pw if pw > 0 else 0.9,
                "y1": ev.bbox_y1 / ph if ph > 0 else 0.2,
            }

        is_this_focused = (str(f.id) == focused_id)
        nodes.append({
            "id": str(f.id),
            "type": "fact",
            "label": f"{f.predicate}: {f.object_value}",
            "entity_name": f.subject,
            "predicate": f.predicate,
            "value": f.object_value,
            "unit": f.unit,
            "currency": f.currency,
            "fiscal_year": f.fiscal_year,
            "fiscal_quarter": f.fiscal_quarter,
            "category": f.category or "General",
            "basis": f.basis or "GAAP",
            "scope": f.scope or "Consolidated",
            "confidence": f.confidence or 0.95,
            "is_uncertain": bool(f.is_uncertain),
            "document_id": str(f.document_id),
            "document_name": doc.original_filename if doc else "Source Document",
            "page_number": ev.page_number if ev else 1,
            "snippet": ev.excerpt if ev else (f.original_text or f.object_value or ""),
            "bbox": bbox,
            "is_focused": is_this_focused,
        })

        # Connect Entity -> Fact
        edges.append({
            "id": f"ef-{f.subject}-{f.id}",
            "source": f"entity-{f.subject}",
            "target": str(f.id),
            "type": "HAS_FACT",
            "label": "has claim",
        })

        # Connect Document -> Fact
        if f.document_id and f.document_id in doc_map:
            page_num = ev.page_number if ev else 1
            edges.append({
                "id": f"df-{f.document_id}-{f.id}",
                "source": f"doc-{f.document_id}",
                "target": str(f.id),
                "type": "EXTRACTED_FROM",
                "label": f"Page {page_num}",
                "page_number": page_num,
            })

    # D. Cross-Document Relationship Edges between Facts
    for r in selected_relationships:
        if r.fact_a_id in fact_map and r.fact_b_id in fact_map:
            fa = fact_map[r.fact_a_id]
            fb = fact_map[r.fact_b_id]
            doc_a = doc_map.get(fa.document_id)
            doc_b = doc_map.get(fb.document_id)

            edges.append({
                "id": f"rel-{r.id}",
                "rel_id": str(r.id),
                "source": str(r.fact_a_id),
                "target": str(r.fact_b_id),
                "type": r.relationship_type,
                "label": r.relationship_type,
                "confidence": r.confidence or 0.9,
                "explanation": r.explanation or "",
                "reasoning_trace": r.reasoning_trace,
                "context_difference_type": r.context_difference_type,
                "supersession_date": r.supersession_date,
                "classification_method": r.classification_method or "deterministic",
                "is_cross_document": bool(fa.document_id != fb.document_id),
                "fact_a_subject": fa.subject,
                "fact_a_predicate": fa.predicate,
                "fact_a_value": fa.object_value,
                "fact_a_doc": doc_a.original_filename if doc_a else "Doc A",
                "fact_b_subject": fb.subject,
                "fact_b_predicate": fb.predicate,
                "fact_b_value": fb.object_value,
                "fact_b_doc": doc_b.original_filename if doc_b else "Doc B",
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            **stats,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "fact_count": len(all_facts),
            "entity_count": len(entities_present),
            "document_count": len(doc_map),
        },
        "focused_id": focused_id,
        "focused_entity": focused_entity,
        "filter_scope": filter_scope,
    }


@router.get("/graph/entities")
async def list_graph_entities(
    limit: int = Query(50, ge=5, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    List distinct entities in the knowledge graph with their fact counts,
    active cross-document relationships, and contradiction totals.
    """
    # Fetch distinct subjects with fact count
    stmt = (
        select(Fact.subject, func.count(Fact.id))
        .where(Fact.is_canonical == True)
        .group_by(Fact.subject)
        .order_by(desc(func.count(Fact.id)))
        .limit(limit)
    )
    res = await db.execute(stmt)
    rows = res.all()

    items = []
    for subject, f_cnt in rows:
        # Count contradictions for subject
        contra_stmt = (
            select(func.count(FactRelationship.id))
            .join(Fact, or_(FactRelationship.fact_a_id == Fact.id, FactRelationship.fact_b_id == Fact.id))
            .where(
                and_(
                    Fact.subject == subject,
                    FactRelationship.relationship_type == "CONTRADICTS",
                )
            )
        )
        c_res = await db.execute(contra_stmt)
        contra_count = c_res.scalar() or 0

        # Count corroborations
        corrob_stmt = (
            select(func.count(FactRelationship.id))
            .join(Fact, or_(FactRelationship.fact_a_id == Fact.id, FactRelationship.fact_b_id == Fact.id))
            .where(
                and_(
                    Fact.subject == subject,
                    FactRelationship.relationship_type == "CORROBORATES",
                )
            )
        )
        cor_res = await db.execute(corrob_stmt)
        corrob_count = cor_res.scalar() or 0

        items.append({
            "name": subject,
            "facts_count": f_cnt,
            "contradictions_count": contra_count,
            "corroborations_count": corrob_count,
            "total_relationships": contra_count + corrob_count,
        })

    return {"items": items, "total": len(items)}


@router.get("/graph/stats")
async def get_graph_overview_stats(db: AsyncSession = Depends(get_db)):
    """Summary metrics of the global Knowledge Graph."""
    fact_cnt = (await db.execute(select(func.count(Fact.id)))).scalar() or 0
    rel_cnt = (await db.execute(select(func.count(FactRelationship.id)))).scalar() or 0
    doc_cnt = (await db.execute(select(func.count(Document.id)))).scalar() or 0
    contra_cnt = (
        await db.execute(
            select(func.count(FactRelationship.id)).where(FactRelationship.relationship_type == "CONTRADICTS")
        )
    ).scalar() or 0
    corrob_cnt = (
        await db.execute(
            select(func.count(FactRelationship.id)).where(FactRelationship.relationship_type == "CORROBORATES")
        )
    ).scalar() or 0
    super_cnt = (
        await db.execute(
            select(func.count(FactRelationship.id)).where(FactRelationship.relationship_type == "SUPERSEDES")
        )
    ).scalar() or 0

    return {
        "total_facts": fact_cnt,
        "total_relationships": rel_cnt,
        "total_documents": doc_cnt,
        "contradictions": contra_cnt,
        "corroborations": corrob_cnt,
        "superseded": super_cnt,
    }
