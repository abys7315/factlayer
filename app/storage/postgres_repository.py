"""PostgreSQL repository with idempotent operations."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import select, update, func, and_, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Document, DocumentPage, DocumentSection, ContentBlock, Figure,
    Entity, EntityAlias, Fact, Evidence, FactRelationship, ProcessingJob,
)


class PostgresRepository:
    """Repository pattern for all PostgreSQL operations. Async via SQLAlchemy + asyncpg."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Documents ─────────────────────────────────────────────────────

    async def create_document(self, **kwargs) -> Document:
        doc = Document(**kwargs)
        self.session.add(doc)
        await self.session.flush()
        return doc

    async def get_document(self, doc_id: uuid.UUID) -> Document | None:
        result = await self.session.execute(select(Document).where(Document.id == doc_id))
        return result.scalar_one_or_none()

    async def get_document_by_hash(self, file_hash: str) -> Document | None:
        result = await self.session.execute(select(Document).where(Document.file_hash == file_hash))
        return result.scalar_one_or_none()

    async def list_documents(self, limit: int = 100, offset: int = 0) -> Sequence[Document]:
        result = await self.session.execute(
            select(Document).order_by(Document.created_at.desc()).limit(limit).offset(offset)
        )
        return result.scalars().all()

    async def count_documents(self) -> int:
        result = await self.session.execute(select(func.count(Document.id)))
        return result.scalar_one()

    async def update_document(self, doc_id: uuid.UUID, **kwargs) -> None:
        await self.session.execute(
            update(Document).where(Document.id == doc_id).values(**kwargs, updated_at=datetime.utcnow())
        )

    async def delete_document(self, doc_id: uuid.UUID) -> None:
        doc = await self.get_document(doc_id)
        if doc:
            await self.session.delete(doc)

    # ── Pages ─────────────────────────────────────────────────────────

    async def create_page(self, **kwargs) -> DocumentPage:
        page = DocumentPage(**kwargs)
        self.session.add(page)
        await self.session.flush()
        return page

    async def get_pages_by_document(self, doc_id: uuid.UUID) -> Sequence[DocumentPage]:
        result = await self.session.execute(
            select(DocumentPage).where(DocumentPage.document_id == doc_id).order_by(DocumentPage.page_number)
        )
        return result.scalars().all()

    async def update_page(self, page_id: uuid.UUID, **kwargs) -> None:
        await self.session.execute(
            update(DocumentPage).where(DocumentPage.id == page_id).values(**kwargs)
        )

    # ── Sections ──────────────────────────────────────────────────────

    async def create_section(self, **kwargs) -> DocumentSection:
        section = DocumentSection(**kwargs)
        self.session.add(section)
        await self.session.flush()
        return section

    # ── Blocks ────────────────────────────────────────────────────────

    async def create_block(self, **kwargs) -> ContentBlock:
        block = ContentBlock(**kwargs)
        self.session.add(block)
        await self.session.flush()
        return block

    # ── Figures ───────────────────────────────────────────────────────

    async def create_figure(self, **kwargs) -> Figure:
        fig = Figure(**kwargs)
        self.session.add(fig)
        await self.session.flush()
        return fig

    # ── Entities ──────────────────────────────────────────────────────

    async def create_entity(self, **kwargs) -> Entity:
        entity = Entity(**kwargs)
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def get_entity_by_name(self, name: str) -> Entity | None:
        result = await self.session.execute(select(Entity).where(Entity.canonical_name == name))
        return result.scalar_one_or_none()

    async def find_entity_by_alias(self, alias: str) -> Entity | None:
        result = await self.session.execute(
            select(Entity).join(EntityAlias).where(
                func.lower(EntityAlias.alias) == alias.lower()
            )
        )
        return result.scalar_one_or_none()

    async def create_alias(self, **kwargs) -> EntityAlias:
        alias = EntityAlias(**kwargs)
        self.session.add(alias)
        await self.session.flush()
        return alias

    # ── Facts ─────────────────────────────────────────────────────────

    async def upsert_fact(self, fact_data: dict) -> tuple[Fact, bool]:
        """Idempotent fact insertion using content_hash. Returns (fact, is_new)."""
        content_hash = fact_data.get("content_hash", "")
        if content_hash:
            existing = await self.session.execute(
                select(Fact).where(Fact.content_hash == content_hash)
            )
            existing_fact = existing.scalar_one_or_none()
            if existing_fact:
                return existing_fact, False

        fact = Fact(**fact_data)
        self.session.add(fact)
        await self.session.flush()
        return fact, True

    async def get_fact(self, fact_id: uuid.UUID) -> Fact | None:
        result = await self.session.execute(select(Fact).where(Fact.id == fact_id))
        return result.scalar_one_or_none()

    async def get_facts_by_document(self, doc_id: uuid.UUID) -> Sequence[Fact]:
        result = await self.session.execute(
            select(Fact).where(and_(Fact.document_id == doc_id, Fact.is_canonical == True))
            .order_by(Fact.created_at)
        )
        return result.scalars().all()

    async def get_facts_by_fingerprint(self, fingerprint: str) -> Sequence[Fact]:
        result = await self.session.execute(
            select(Fact).where(Fact.context_fingerprint == fingerprint)
        )
        return result.scalars().all()

    async def get_facts_by_entity_predicate(
        self, entity_id: uuid.UUID, predicate: str
    ) -> Sequence[Fact]:
        result = await self.session.execute(
            select(Fact).where(and_(
                Fact.entity_id == entity_id,
                Fact.predicate == predicate,
                Fact.is_canonical == True,
            ))
        )
        return result.scalars().all()

    async def get_all_facts(
        self, limit: int = 1000, offset: int = 0,
        entity_id: uuid.UUID | None = None,
        document_id: uuid.UUID | None = None,
        relationship_type: str | None = None,
    ) -> Sequence[Fact]:
        query = select(Fact).where(Fact.is_canonical == True)
        if entity_id:
            query = query.where(Fact.entity_id == entity_id)
        if document_id:
            query = query.where(Fact.document_id == document_id)
        query = query.order_by(Fact.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count_facts(self, document_id: uuid.UUID | None = None) -> int:
        query = select(func.count(Fact.id)).where(Fact.is_canonical == True)
        if document_id:
            query = query.where(Fact.document_id == document_id)
        result = await self.session.execute(query)
        return result.scalar_one()

    # ── Evidence ──────────────────────────────────────────────────────

    async def create_evidence(self, **kwargs) -> Evidence:
        ev = Evidence(**kwargs)
        self.session.add(ev)
        await self.session.flush()
        return ev

    async def get_evidence_for_fact(self, fact_id: uuid.UUID) -> Sequence[Evidence]:
        result = await self.session.execute(
            select(Evidence).where(Evidence.fact_id == fact_id).order_by(Evidence.page_number)
        )
        return result.scalars().all()

    async def get_evidence_for_page(
        self, doc_id: uuid.UUID, page_number: int
    ) -> Sequence[Evidence]:
        result = await self.session.execute(
            select(Evidence).where(and_(
                Evidence.document_id == doc_id,
                Evidence.page_number == page_number,
            ))
        )
        return result.scalars().all()

    # ── Relationships ─────────────────────────────────────────────────

    async def create_relationship(self, **kwargs) -> FactRelationship:
        rel = FactRelationship(**kwargs)
        self.session.add(rel)
        await self.session.flush()
        return rel

    async def get_relationship(self, rel_id: uuid.UUID) -> FactRelationship | None:
        result = await self.session.execute(
            select(FactRelationship).where(FactRelationship.id == rel_id)
        )
        return result.scalar_one_or_none()

    async def get_relationships_for_fact(self, fact_id: uuid.UUID) -> Sequence[FactRelationship]:
        result = await self.session.execute(
            select(FactRelationship).where(or_(
                FactRelationship.fact_a_id == fact_id,
                FactRelationship.fact_b_id == fact_id,
            ))
        )
        return result.scalars().all()

    async def get_relationships_by_type(
        self, rel_type: str, limit: int = 100, offset: int = 0
    ) -> Sequence[FactRelationship]:
        result = await self.session.execute(
            select(FactRelationship).where(FactRelationship.relationship_type == rel_type)
            .order_by(FactRelationship.confidence.desc())
            .limit(limit).offset(offset)
        )
        return result.scalars().all()

    async def get_all_relationships(
        self, limit: int = 100, offset: int = 0,
        rel_type: str | None = None,
    ) -> Sequence[FactRelationship]:
        query = select(FactRelationship)
        if rel_type:
            query = query.where(FactRelationship.relationship_type == rel_type)
        query = query.order_by(FactRelationship.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count_relationships(self, rel_type: str | None = None) -> int:
        query = select(func.count(FactRelationship.id))
        if rel_type:
            query = query.where(FactRelationship.relationship_type == rel_type)
        result = await self.session.execute(query)
        return result.scalar_one()

    async def relationship_exists(self, fact_a_id: uuid.UUID, fact_b_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            select(func.count(FactRelationship.id)).where(or_(
                and_(FactRelationship.fact_a_id == fact_a_id, FactRelationship.fact_b_id == fact_b_id),
                and_(FactRelationship.fact_a_id == fact_b_id, FactRelationship.fact_b_id == fact_a_id),
            ))
        )
        return result.scalar_one() > 0

    # ── Processing Jobs ───────────────────────────────────────────────

    async def create_job(self, **kwargs) -> ProcessingJob:
        job = ProcessingJob(**kwargs)
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_job(self, job_id: uuid.UUID) -> ProcessingJob | None:
        result = await self.session.execute(select(ProcessingJob).where(ProcessingJob.id == job_id))
        return result.scalar_one_or_none()

    async def update_job(self, job_id: uuid.UUID, **kwargs) -> None:
        await self.session.execute(
            update(ProcessingJob).where(ProcessingJob.id == job_id).values(**kwargs)
        )
