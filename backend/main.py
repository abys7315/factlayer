"""FastAPI application entry point for Fact Knowledge Layer."""

from __future__ import annotations
import os
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from backend.db import init_db, get_db, Document, Fact, Relationship
from backend.failure_detector import (
    log_failure,
    check_extraction_completeness,
    flag_low_confidence_relationships,
    get_failure_report,
)
from backend.models import (
    DocumentResponse,
    FactResponse,
    RelationshipResponse,
    FactDetailResponse,
    FailureReportResponse,
    UploadResponse,
)
from backend.pdf_parser import PDFParser
from backend.fact_extractor import FactExtractor
from backend.embeddings import EmbeddingGenerator
from backend.matcher import FactMatcher
from backend.relationship_classifier import RelationshipClassifier

load_dotenv()

# Initialize DB tables on startup
init_db()

app = FastAPI(
    title="Fact Knowledge Layer API",
    description="Cross-document fact extraction, grounding, and relationship reasoning pipeline",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Storage paths
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Processing components
pdf_parser = PDFParser()
fact_extractor = FactExtractor()
embedding_gen = EmbeddingGenerator()
matcher = FactMatcher(top_k=5, similarity_threshold=0.55)
rel_classifier = RelationshipClassifier()


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "api": "healthy",
        "llm": "configured" if (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) else "deterministic_fallback",
        "embeddings": "local_sentence_transformers",
    }


def process_document_pipeline(doc_id: int, saved_path: Path, db: Session):
    """Core fact extraction + embedding + cross-doc relationship pipeline."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        return

    try:
        # Step 1: Parse PDF
        parsed = pdf_parser.parse_pdf(saved_path)
        doc.page_count = parsed["page_count"]
        db.commit()

        # Step 2: Extract facts from each chunk & audit completeness
        new_facts = []
        for chunk in parsed["chunks"]:
            extracted = fact_extractor.extract_facts(chunk["text"], chunk["page_number"], bbox=chunk.get("bbox"))
            # Completeness audit on extracted facts vs page numeric density
            check_extraction_completeness(
                page_text=chunk["text"],
                extracted_facts=extracted,
                page_number=chunk["page_number"],
                db=db,
            )

            for f_data in extracted:
                fact_obj = Fact(
                    doc_id=doc.id,
                    fact_text=f_data["fact_text"],
                    fact_type=f_data.get("fact_type", "general"),
                    fact_type_reasoning=f_data.get("fact_type_reasoning"),
                    value=f_data.get("value"),
                    unit=f_data.get("unit"),
                    time_period=f_data.get("time_period"),
                    source_quote=f_data["source_quote"],
                    page_number=f_data["page_number"],
                )
                if f_data.get("bbox"):
                    fact_obj.set_bbox(f_data["bbox"])
                # Step 3: Generate and store embedding
                emb = embedding_gen.generate_embedding(f_data["fact_text"])
                fact_obj.set_embedding(emb)
                db.add(fact_obj)
                new_facts.append(fact_obj)

        db.commit()
        for f in new_facts:
            db.refresh(f)

        # Step 4: Cross-document matching & 5-factor relationship classification
        all_existing_facts = db.query(Fact).all()
        new_relationships = []
        for new_f in new_facts:
            candidate_matches = matcher.find_matches(
                target_fact=new_f,
                all_facts=all_existing_facts,
                exclude_same_doc=False,
            )
            for other_fact, sim_score in candidate_matches:
                # Check if relationship already exists
                existing_rel = db.query(Relationship).filter(
                    ((Relationship.fact_id_1 == new_f.id) & (Relationship.fact_id_2 == other_fact.id)) |
                    ((Relationship.fact_id_1 == other_fact.id) & (Relationship.fact_id_2 == new_f.id))
                ).first()
                if existing_rel:
                    continue

                classification = rel_classifier.classify_relationship(new_f, other_fact)
                if classification["relationship_type"] != "unrelated":
                    rel_obj = Relationship(
                        fact_id_1=new_f.id,
                        fact_id_2=other_fact.id,
                        relationship_type=classification["relationship_type"],
                        explanation=classification["explanation"],
                        confidence=classification.get("confidence", 0.95),
                    )
                    if classification.get("reconciling_factors"):
                        rel_obj.set_reconciling_factors(classification["reconciling_factors"])
                    db.add(rel_obj)
                    new_relationships.append({
                        "fact_id_1": new_f.id,
                        "fact_id_2": other_fact.id,
                        "relationship_type": classification["relationship_type"],
                        "confidence": classification.get("confidence", 0.95),
                    })

        # Step 5: Flag low confidence relationships
        if new_relationships:
            flag_low_confidence_relationships(new_relationships, threshold=0.50, db=db)

        db.commit()

    except Exception as e:
        db.rollback()
        raise e


@app.post("/upload", response_model=UploadResponse)
def upload_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a PDF file and process facts + cross-document relationships."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    saved_path = UPLOAD_DIR / file.filename
    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Create document record
    doc = Document(
        filename=file.filename,
        raw_text_path=str(saved_path),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Run processing pipeline
    process_document_pipeline(doc.id, saved_path, db)

    # Count outcomes
    facts_count = db.query(Fact).filter(Fact.doc_id == doc.id).count()
    rels_count = db.query(Relationship).filter(
        (Relationship.fact_id_1.in_(db.query(Fact.id).filter(Fact.doc_id == doc.id))) |
        (Relationship.fact_id_2.in_(db.query(Fact.id).filter(Fact.doc_id == doc.id)))
    ).count()

    return UploadResponse(
        document_id=doc.id,
        filename=doc.filename,
        page_count=doc.page_count,
        facts_extracted=facts_count,
        relationships_found=rels_count,
        status="success",
    )


@app.get("/documents", response_model=List[DocumentResponse])
def list_documents(db: Session = Depends(get_db)):
    """List all uploaded documents."""
    return db.query(Document).order_by(Document.id.desc()).all()


@app.get("/facts", response_model=List[FactResponse])
def list_facts(
    doc_id: Optional[int] = Query(None, description="Filter by document ID"),
    fact_type: Optional[str] = Query(None, description="Filter by fact type"),
    db: Session = Depends(get_db),
):
    """List extracted facts with optional document and type filtering."""
    query = db.query(Fact)
    if doc_id is not None:
        query = query.filter(Fact.doc_id == doc_id)
    if fact_type is not None:
        query = query.filter(Fact.fact_type == fact_type)

    facts = query.order_by(Fact.id.desc()).all()
    out = []
    for f in facts:
        resp = FactResponse.from_orm(f)
        resp.bbox = f.get_bbox()
        if f.document:
            resp.document_filename = f.document.filename
        out.append(resp)
    return out


@app.get("/facts/{fact_id}", response_model=FactDetailResponse)
def get_fact(fact_id: int, db: Session = Depends(get_db)):
    """Get single fact details, source quote, and all linked relationships."""
    fact = db.query(Fact).filter(Fact.id == fact_id).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")

    rels = db.query(Relationship).filter(
        (Relationship.fact_id_1 == fact_id) | (Relationship.fact_id_2 == fact_id)
    ).all()

    rel_responses = []
    for r in rels:
        r_resp = RelationshipResponse.from_orm(r)
        if r.fact_1:
            f1 = FactResponse.from_orm(r.fact_1)
            f1.bbox = r.fact_1.get_bbox()
            r_resp.fact_1 = f1
        if r.fact_2:
            f2 = FactResponse.from_orm(r.fact_2)
            f2.bbox = r.fact_2.get_bbox()
            r_resp.fact_2 = f2
        rel_responses.append(r_resp)

    fact_resp = FactDetailResponse.from_orm(fact)
    fact_resp.bbox = fact.get_bbox()
    if fact.document:
        fact_resp.document = DocumentResponse.from_orm(fact.document)
        fact_resp.document_filename = fact.document.filename
    fact_resp.relationships = rel_responses

    return fact_resp


@app.get("/relationships", response_model=List[RelationshipResponse])
def list_relationships(
    type: Optional[str] = Query(None, description="Filter by relationship_type (corroborate, contradict, reconcilable)"),
    db: Session = Depends(get_db),
):
    """List cross-document relationships with optional relationship_type filter."""
    query = db.query(Relationship)
    if type:
        query = query.filter(Relationship.relationship_type == type.lower())

    rels = query.order_by(Relationship.id.desc()).all()
    out = []
    for r in rels:
        r_resp = RelationshipResponse.from_orm(r)
        r_resp.reconciling_factors = r.get_reconciling_factors()
        if r.fact_1:
            f1 = FactResponse.from_orm(r.fact_1)
            f1.bbox = r.fact_1.get_bbox()
            if r.fact_1.document:
                f1.document_filename = r.fact_1.document.filename
            r_resp.fact_1 = f1
        if r.fact_2:
            f2 = FactResponse.from_orm(r.fact_2)
            f2.bbox = r.fact_2.get_bbox()
            if r.fact_2.document:
                f2.document_filename = r.fact_2.document.filename
            r_resp.fact_2 = f2
        out.append(r_resp)
    return out


@app.get("/audit/report", response_model=FailureReportResponse)
def failure_audit_report(db: Session = Depends(get_db)):
    """Retrieve full audit report with failure logs, completeness checks, and low-confidence flags."""
    return get_failure_report(db=db)
