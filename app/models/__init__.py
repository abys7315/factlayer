"""Models package — exports all ORM models for Alembic and application use."""

from app.models.database import Base, get_db, get_engine, get_session_factory, init_db, close_db
from app.models.enums import (
    ProcessingStatus, PIPELINE_STAGES, BlockType, FigureType,
    FactType, ProvenanceQuality, EvidenceType, RelationshipType,
    EntityMatchConfidence, JobStatus,
)
from app.models.document import Document
from app.models.page import DocumentPage
from app.models.section import DocumentSection
from app.models.block import ContentBlock
from app.models.figure import Figure
from app.models.entity import Entity, EntityAlias
from app.models.fact import Fact
from app.models.evidence import Evidence
from app.models.relationship import FactRelationship
from app.models.processing_job import ProcessingJob

__all__ = [
    "Base", "get_db", "get_engine", "get_session_factory", "init_db", "close_db",
    "ProcessingStatus", "PIPELINE_STAGES", "BlockType", "FigureType",
    "FactType", "ProvenanceQuality", "EvidenceType", "RelationshipType",
    "EntityMatchConfidence", "JobStatus",
    "Document", "DocumentPage", "DocumentSection", "ContentBlock",
    "Figure", "Entity", "EntityAlias", "Fact", "Evidence",
    "FactRelationship", "ProcessingJob",
]
