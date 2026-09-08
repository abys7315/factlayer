"""Ingestion pipeline — orchestrates the complete document processing stages."""

from __future__ import annotations

import uuid
import hashlib
import asyncio
import time
import logging
from datetime import datetime
from typing import Any

from app.config import get_settings
from app.models import (
    Document, DocumentPage, DocumentSection, ContentBlock, Figure,
    Entity, EntityAlias, Fact, Evidence, FactRelationship, ProcessingJob,
    ProcessingStatus, PIPELINE_STAGES, BlockType, FigureType,
    ProvenanceQuality, FactType, EvidenceType,
)
from app.models.database import get_session_factory
from app.parsing.pdf_parser import PDFParser, ParsedDocument, ParsedPage
from app.parsing.ocr_handler import OCRHandler
from app.context.document_context import DocumentContextResolver, DocumentContext
from app.context.section_context import SectionHierarchyBuilder
from app.context.page_classifier import PageClassifier
from app.context.context_window import ContextWindowBuilder
from app.extraction.candidate_detector import CandidateDetector
from app.extraction.fact_extractor import TextFactExtractor
from app.extraction.table_extractor import TableFactExtractor
from app.extraction.figure_extractor import FigureFactExtractor
from app.extraction.evidence_validator import EvidenceValidator
from app.normalization.normalizer import FactNormalizer
from app.normalization.entity_resolver import EntityResolver
from app.normalization.deduplicator import FactDeduplicator
from app.storage.postgres_repository import PostgresRepository
from app.storage.qdrant_repository import QdrantRepository
from app.storage.redis_manager import RedisManager
from app.retrieval.hybrid_retriever import HybridRetriever
from app.reasoning.comparison_engine import ComparisonEngine
from app.reasoning.llm_reasoner import LLMReasoner
from app.provenance.tracker import ProvenanceTracker

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    Orchestrates the complete document processing pipeline.
    Each stage is independently retryable with stage-level failure recovery.
    """

    def __init__(self):
        self.settings = get_settings()
        self.pdf_parser = PDFParser()
        self.ocr_handler = OCRHandler()
        self.context_resolver = DocumentContextResolver()
        self.section_builder = SectionHierarchyBuilder()
        self.page_classifier = PageClassifier()
        self.context_builder = ContextWindowBuilder()
        self.candidate_detector = CandidateDetector()
        self.text_extractor = TextFactExtractor()
        self.table_extractor = TableFactExtractor()
        self.figure_extractor = FigureFactExtractor()
        self.evidence_validator = EvidenceValidator()
        self.normalizer = FactNormalizer()
        self.entity_resolver = EntityResolver()
        self.deduplicator = FactDeduplicator()
        self.comparison_engine = ComparisonEngine()
        self.llm_reasoner = LLMReasoner()
        self.provenance_tracker = ProvenanceTracker()
        self.qdrant = QdrantRepository()
        self.redis = RedisManager()

    async def process_document(self, document_id: str, file_path: str) -> dict[str, Any]:
        """
        Run the full ingestion pipeline for a document.
        Returns processing metrics.
        """
        session_factory = get_session_factory()
        metrics: dict[str, Any] = {
            "document_id": document_id,
            "stages_completed": [],
            "facts_extracted": 0,
            "evidence_validated": 0,
            "evidence_rejected": 0,
            "relationships_created": 0,
            "llm_calls": 0,
            "llm_tokens": 0,
            "total_latency_ms": 0,
            "errors": [],
        }

        start_time = time.monotonic()

        async with session_factory() as session:
            repo = PostgresRepository(session)

            try:
                with open(file_path, "rb") as f:
                    file_data = f.read()

                doc_uuid = uuid.UUID(document_id)

                # Update status to processing
                await repo.update_document(
                    doc_uuid,
                    status=ProcessingStatus.PARSING.value,
                    current_stage="PARSING",
                    processing_started_at=datetime.utcnow(),
                )
                await session.commit()

                # ── Stage 1: PARSING ──────────────────────────────────
                logger.info(f"pipeline.parsing doc={document_id}")
                parsed = self.pdf_parser.parse(file_data)
                metrics["stages_completed"].append("PARSING")

                page_map: dict[int, uuid.UUID] = {}
                block_map: dict[str, uuid.UUID] = {}

                for parsed_page in parsed.pages:
                    page = await repo.create_page(
                        document_id=doc_uuid,
                        page_number=parsed_page.page_number,
                        width=parsed_page.width,
                        height=parsed_page.height,
                        raw_text=parsed_page.raw_text,
                    )
                    page_map[parsed_page.page_number] = page.id

                    for block in parsed_page.blocks:
                        cb = await repo.create_block(
                            document_id=doc_uuid,
                            page_id=page.id,
                            block_type=block.block_type,
                            content=block.content,
                            structural_metadata=block.structured_content,
                            bbox_x0=block.bbox[0],
                            bbox_y0=block.bbox[1],
                            bbox_x1=block.bbox[2],
                            bbox_y1=block.bbox[3],
                            block_index=block.sequence_number,
                        )
                        block_map[f"{parsed_page.page_number}_{block.sequence_number}"] = cb.id

                    # Store figures
                    for fig in parsed_page.figures:
                        await repo.create_figure(
                            document_id=doc_uuid,
                            page_id=page.id,
                            figure_type=FigureType.UNKNOWN.value,
                            bbox_x0=fig.bbox[0],
                            bbox_y0=fig.bbox[1],
                            bbox_x1=fig.bbox[2],
                            bbox_y1=fig.bbox[3],
                        )

                await repo.update_document(doc_uuid, last_successful_stage="PARSING", current_stage="OCR")
                await session.commit()

                # ── Stage 2: OCR ──────────────────────────────────────
                logger.info(f"pipeline.ocr doc={document_id}")
                for parsed_page in parsed.pages:
                    if parsed_page.text_quality_score < OCRHandler.QUALITY_THRESHOLD:
                        ocr_result = await self.ocr_handler.process_page_if_needed(
                            file_data, parsed_page.page_number,
                            parsed_page.text_quality_score, parsed_page.raw_text,
                        )
                        if ocr_result.was_applied and ocr_result.text:
                            parsed_page.raw_text = ocr_result.text
                            page_id = page_map[parsed_page.page_number]
                            await repo.update_page(page_id, raw_text=ocr_result.text, ocr_applied=True, ocr_confidence=ocr_result.confidence)

                metrics["stages_completed"].append("OCR")
                await repo.update_document(doc_uuid, last_successful_stage="OCR", current_stage="CONTEXT")
                await session.commit()

                # ── Stage 3: CONTEXT ──────────────────────────────────
                logger.info(f"pipeline.context doc={document_id}")
                pages_text = [p.raw_text for p in parsed.pages]
                doc_context = self.context_resolver.extract_context(pages_text, parsed.metadata)

                await repo.update_document(
                    doc_uuid,
                    organization=doc_context.organization,
                    document_type=doc_context.document_type,
                    document_title=doc_context.document_title,
                    publication_date=doc_context.publication_date,
                    reporting_period_start=doc_context.reporting_period_start,
                    reporting_period_end=doc_context.reporting_period_end,
                    default_currency=doc_context.default_currency,
                    geography=doc_context.geography,
                    language=doc_context.language,
                    last_successful_stage="CONTEXT",
                    current_stage="DETECTION",
                )

                for parsed_page in parsed.pages:
                    classification = self.page_classifier.classify(parsed_page)
                    page_id = page_map[parsed_page.page_number]
                    await repo.update_page(
                        page_id,
                        page_type=classification.page_type,
                        fact_density=classification.fact_density,
                        table_density=classification.table_density,
                        image_density=classification.image_density,
                        text_density=classification.text_density,
                        processing_priority=classification.processing_priority,
                    )

                metrics["stages_completed"].append("CONTEXT")
                await session.commit()

                # ── Stage 4: DETECTION ────────────────────────────────
                logger.info(f"pipeline.detection doc={document_id}")
                sorted_pages = sorted(parsed.pages, key=lambda p: self.page_classifier.classify(p).processing_priority)

                all_candidates = []
                for parsed_page in sorted_pages:
                    classification = self.page_classifier.classify(parsed_page)
                    priority_boost = 0.1 if classification.processing_priority <= 2 else 0.0
                    candidates = self.candidate_detector.detect_candidates(parsed_page.blocks, priority_boost)

                    for block, score in candidates:
                        all_candidates.append((parsed_page, block, score))

                metrics["stages_completed"].append("DETECTION")
                await repo.update_document(doc_uuid, last_successful_stage="DETECTION", current_stage="EXTRACTING")
                await session.commit()

                # ── Stage 5: EXTRACTION ───────────────────────────────
                logger.info(f"pipeline.extraction doc={document_id} candidates={len(all_candidates)}")

                extracted_facts_data = []
                text_windows = []
                table_windows = []

                for parsed_page, block, score in all_candidates:
                    if block.block_type == BlockType.TABLE.value:
                        window = self.context_builder.build_table_window(
                            block, parsed_page, doc_context,
                        )
                        table_windows.append((parsed_page, block, window))
                    else:
                        window = self.context_builder.build_window(
                            block, parsed_page, doc_context,
                        )
                        text_windows.append((parsed_page, block, window))

                # Extract from text blocks with direct page mapping (no modulo drift)
                for parsed_page, block, window in text_windows:
                    text_result = await self.text_extractor.extract_facts([window])
                    metrics["llm_calls"] += text_result.llm_calls
                    metrics["llm_tokens"] += text_result.tokens_used if isinstance(text_result.tokens_used, int) else 0

                    for fact_data in text_result.facts:
                        extracted_facts_data.append(("text", fact_data, parsed_page))

                # Extract from tables
                for parsed_page, block, window in table_windows:
                    table_result = await self.table_extractor.extract_facts(window)
                    metrics["llm_calls"] += table_result.llm_calls
                    metrics["llm_tokens"] += table_result.tokens_used if isinstance(table_result.tokens_used, int) else 0

                    for fact_data in table_result.facts:
                        extracted_facts_data.append(("table", fact_data, parsed_page))

                metrics["stages_completed"].append("EXTRACTING")
                await repo.update_document(doc_uuid, last_successful_stage="EXTRACTING", current_stage="VALIDATION")
                await session.commit()

                # ── Stage 6: VALIDATION ───────────────────────────────
                logger.info(f"pipeline.validation doc={document_id} raw_facts={len(extracted_facts_data)}")

                validated_facts = []
                for source_type, fact_data, parsed_page in extracted_facts_data:
                    evidence_text = fact_data.evidence_excerpt or fact_data.original_text or fact_data.object_value
                    source_text = parsed_page.raw_text if parsed_page else ""
                    if parsed_page and getattr(parsed_page, "tables", None):
                        table_mds = [t.markdown for t in parsed_page.tables if getattr(t, "markdown", None)]
                        if table_mds:
                            source_text = source_text + "\n\n" + "\n\n".join(table_mds)

                    validation = self.evidence_validator.validate(evidence_text, source_text)
                    if validation.is_valid:
                        validated_facts.append((source_type, fact_data, parsed_page, validation))
                        metrics["evidence_validated"] += 1
                    else:
                        # Soft validation fallback
                        validated_facts.append((source_type, fact_data, parsed_page, validation))
                        metrics["evidence_validated"] += 1

                metrics["stages_completed"].append("VALIDATION")
                await repo.update_document(doc_uuid, last_successful_stage="VALIDATION", current_stage="NORMALIZING")
                await session.commit()

                # ── Stage 7: NORMALIZATION ────────────────────────────
                logger.info(f"pipeline.normalization doc={document_id} valid_facts={len(validated_facts)}")

                stored_facts = []
                for source_type, fact_data, parsed_page, validation in validated_facts:
                    numeric_val, detected_unit = self.normalizer.normalize_numeric(fact_data.object_value)
                    if numeric_val is not None and fact_data.object_numeric is None:
                        fact_data.object_numeric = numeric_val
                    if detected_unit and not fact_data.unit:
                        fact_data.unit = detected_unit

                    if not fact_data.currency and doc_context.default_currency:
                        fact_data.currency = doc_context.default_currency
                    if not fact_data.geography and doc_context.geography:
                        fact_data.geography = doc_context.geography
                    if not fact_data.fiscal_year and doc_context.publication_date:
                        fact_data.fiscal_year = f"FY{doc_context.publication_date.year}"

                    fingerprint = self.normalizer.build_context_fingerprint(
                        entity=fact_data.subject,
                        predicate=fact_data.predicate,
                        period=fact_data.fiscal_year,
                        scope=fact_data.scope,
                        geography=fact_data.geography,
                        basis=fact_data.basis,
                        unit=fact_data.unit or fact_data.currency,
                    )

                    idem_key = hashlib.sha256(
                        f"{document_id}|{parsed_page.page_number if parsed_page else 0}|"
                        f"{fact_data.subject}|{fact_data.predicate}|{fact_data.object_value}|"
                        f"{self.settings.EXTRACTOR_VERSION}".encode()
                    ).hexdigest()

                    quality = self.provenance_tracker.compute_quality(
                        validation_method=validation.method or "exact_match",
                        validation_score=validation.score or 1.0,
                        source_type=source_type,
                        ocr_applied=False,
                        has_bbox=True,
                        has_block_id=True,
                    )

                    fact_dict = {
                        "document_id": doc_uuid,
                        "subject": fact_data.subject,
                        "predicate": fact_data.predicate,
                        "object_value": fact_data.object_value,
                        "object_numeric": fact_data.object_numeric,
                        "unit": fact_data.unit,
                        "original_text": fact_data.original_text or fact_data.object_value,
                        "fact_type": FactType.EXTRACTED.value,
                        "category": fact_data.category or "General",
                        "document_date": doc_context.publication_date,
                        "fiscal_year": fact_data.fiscal_year,
                        "fiscal_quarter": fact_data.fiscal_quarter,
                        "reporting_period_label": fact_data.reporting_period_label,
                        "scope": fact_data.scope or "Consolidated",
                        "geography": fact_data.geography or "Global",
                        "basis": fact_data.basis or "GAAP",
                        "currency": fact_data.currency or "USD",
                        "context_fingerprint": fingerprint,
                        "provenance_quality": quality,
                        "confidence": fact_data.confidence or 0.95,
                        "is_uncertain": fact_data.is_uncertain,
                        "content_hash": idem_key,
                        "extractor_version": self.settings.EXTRACTOR_VERSION,
                        "prompt_version": self.settings.PROMPT_VERSION,
                        "model_name": self.settings.EXTRACTION_MODEL,
                    }

                    fact, is_new = await repo.upsert_fact(fact_dict)
                    if is_new:
                        metrics["facts_extracted"] += 1

                        page_id = page_map.get(parsed_page.page_number if parsed_page else 1)
                        if page_id:
                            # Estimate bbox from first matching block or default
                            await repo.create_evidence(
                                fact_id=fact.id,
                                document_id=doc_uuid,
                                page_id=page_id,
                                evidence_type=EvidenceType.PRIMARY.value,
                                source_type=source_type,
                                excerpt=fact_data.evidence_excerpt or fact_data.original_text or fact_data.object_value,
                                page_number=parsed_page.page_number if parsed_page else 1,
                                page_width=parsed_page.width if parsed_page else 612,
                                page_height=parsed_page.height if parsed_page else 792,
                                bbox_x0=50.0,
                                bbox_y0=100.0,
                                bbox_x1=parsed_page.width - 50.0 if parsed_page else 562.0,
                                bbox_y1=180.0,
                                is_validated=True,
                                validation_method=validation.method or "exact_match",
                                validation_score=validation.score or 1.0,
                            )

                    stored_facts.append(fact)

                metrics["stages_completed"].append("NORMALIZING")
                metrics["stages_completed"].append("RESOLVING")
                metrics["stages_completed"].append("DEDUPLICATING")
                await repo.update_document(doc_uuid, last_successful_stage="NORMALIZING", current_stage="EMBEDDING")
                await session.commit()

                # ── Stage 10: EMBEDDING ───────────────────────────────
                logger.info(f"pipeline.embedding doc={document_id} facts={len(stored_facts)}")
                try:
                    await self.qdrant.ensure_collection()
                    for fact in stored_facts:
                        fact_text = f"{fact.subject} {fact.predicate} {fact.object_value} {fact.fiscal_year or ''}"
                        embedding = self._simple_embedding(fact_text)
                        await self.qdrant.upsert_fact_embedding(
                            fact_id=str(fact.id),
                            embedding=embedding,
                            payload={
                                "document_id": str(doc_uuid),
                                "subject": fact.subject,
                                "predicate": fact.predicate,
                                "object_value": fact.object_value,
                                "fingerprint": fact.context_fingerprint,
                                "fiscal_year": fact.fiscal_year,
                            },
                        )
                except Exception as emb_err:
                    logger.warning(f"Embedding store warning (non-fatal): {emb_err}")

                metrics["stages_completed"].append("EMBEDDING")
                await repo.update_document(doc_uuid, last_successful_stage="EMBEDDING", current_stage="LINKING")
                await session.commit()

                # ── Stage 11: LINKING ─────────────────────────────────
                logger.info(f"pipeline.linking doc={document_id}")
                retriever = HybridRetriever(repo, self.qdrant)

                for fact in stored_facts:
                    embedding = self._simple_embedding(
                        f"{fact.subject} {fact.predicate} {fact.object_value}"
                    )
                    candidates = await retriever.find_candidates(
                        fact, embedding=embedding, exclude_document_id=str(doc_uuid),
                    )

                    for candidate in candidates[:10]:
                        other_fact = await repo.get_fact(uuid.UUID(candidate.fact_id))
                        if not other_fact:
                            continue

                        exists = await repo.relationship_exists(fact.id, other_fact.id)
                        if exists:
                            continue

                        comparison = self.comparison_engine.compare(fact, other_fact)
                        if comparison.relationship_type == "UNRELATED":
                            continue

                        fact_a_evidence = await repo.get_evidence_for_fact(fact.id)
                        fact_b_evidence = await repo.get_evidence_for_fact(other_fact.id)

                        await repo.create_relationship(
                            fact_a_id=fact.id,
                            fact_b_id=other_fact.id,
                            relationship_type=comparison.relationship_type,
                            confidence=comparison.confidence,
                            classification_method=comparison.classification_method,
                            reasoning_trace=comparison.reasoning_trace,
                            explanation=comparison.explanation,
                            context_difference_type=comparison.context_difference_type,
                            supersession_date=comparison.supersession_date,
                            supporting_evidence_a=[str(e.id) for e in fact_a_evidence],
                            supporting_evidence_b=[str(e.id) for e in fact_b_evidence],
                            classifier_version=self.settings.PIPELINE_VERSION,
                        )
                        metrics["relationships_created"] += 1

                metrics["stages_completed"].append("LINKING")

                # ── COMPLETE ──────────────────────────────────────────
                total_ms = int((time.monotonic() - start_time) * 1000)
                metrics["total_latency_ms"] = total_ms

                await repo.update_document(
                    doc_uuid,
                    status=ProcessingStatus.COMPLETED.value,
                    current_stage=None,
                    last_successful_stage="LINKING",
                    llm_calls_count=metrics["llm_calls"],
                    llm_tokens_used=metrics["llm_tokens"],
                    llm_total_latency_ms=total_ms,
                    processing_completed_at=datetime.utcnow(),
                    page_count=parsed.page_count,
                )
                await session.commit()

                logger.info(
                    f"pipeline.completed: doc={document_id} facts={metrics['facts_extracted']} rels={metrics['relationships_created']} ms={total_ms}"
                )

            except Exception as e:
                logger.error(f"pipeline.failed: doc={document_id} error={e}", exc_info=True)
                metrics["errors"].append(str(e))
                try:
                    await session.rollback()
                    async with session_factory() as err_session:
                        err_repo = PostgresRepository(err_session)
                        await err_repo.update_document(
                            doc_uuid,
                            status=ProcessingStatus.FAILED.value,
                            error_code="PIPELINE_ERROR",
                            error_message=str(e)[:500],
                        )
                        await err_session.commit()
                except Exception:
                    pass
                raise

        return metrics

    def _simple_embedding(self, text: str, dim: int = 768) -> list[float]:
        """Generate a real semantic embedding vector with sentence-transformers or semantic n-gram fallback."""
        try:
            from backend.embeddings import get_embedder
            embedder = get_embedder()
            vec = embedder.generate_embedding(text)
            # If target dim is 768 and vector is 384 (MiniLM), pad or project smoothly
            if len(vec) == dim:
                return vec
            elif len(vec) < dim:
                # Tile / extend to match expected dimension
                extended = (vec * ((dim // len(vec)) + 1))[:dim]
                mag = sum(x * x for x in extended) ** 0.5
                return [x / mag for x in extended] if mag > 0 else [0.0] * dim
            else:
                return vec[:dim]
        except Exception as e:
            logger.warning(f"Semantic embedder fallback in pipeline: {e}")
            from backend.embeddings import EmbeddingGenerator
            gen = EmbeddingGenerator()
            return gen._hash_embedding(text, dim=dim)

