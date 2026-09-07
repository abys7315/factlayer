"""Viewer routes — PDF rendering and evidence overlay coordinates."""

from __future__ import annotations

import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.database import get_db
from app.models.document import Document
from app.models.fact import Fact
from app.models.evidence import Evidence
from app.storage.postgres_repository import PostgresRepository
from app.api.schemas.responses import EvidenceResponse, ViewerOverlayResponse, ViewerOverlayItem
from app.config import get_settings

import fitz  # PyMuPDF
from fastapi.responses import FileResponse, Response

router = APIRouter()


@router.get("/viewer/{doc_id}/pdf")
@router.get("/documents/{doc_id}/pdf")
async def serve_pdf(doc_id: str, db: AsyncSession = Depends(get_db)):
    """Serve the original PDF file for inline viewing."""
    repo = PostgresRepository(db)
    doc = await repo.get_document(uuid.UUID(doc_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    settings = get_settings()
    file_path = Path(settings.UPLOAD_DIR) / doc.filename
    if not file_path.exists():
        fixtures_dir = Path("tests/fixtures/synthetic")
        fallback = fixtures_dir / doc.filename
        if fallback.exists():
            file_path = fallback
        else:
            raise HTTPException(status_code=404, detail="PDF file not found on disk")

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        content_disposition_type="inline",
    )


@router.get("/viewer/{doc_id}/page/{page_number}/image")
@router.get("/documents/{doc_id}/page/{page_number}/image")
async def render_page_image(
    doc_id: str,
    page_number: int,
    dpi: int = Query(150, description="DPI resolution for rendering"),
    db: AsyncSession = Depends(get_db),
):
    """Render a specific PDF page as high-resolution PNG image."""
    repo = PostgresRepository(db)
    doc = await repo.get_document(uuid.UUID(doc_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    settings = get_settings()
    file_path = Path(settings.UPLOAD_DIR) / doc.filename
    if not file_path.exists():
        fixtures_dir = Path("tests/fixtures/synthetic")
        fallback = fixtures_dir / doc.filename
        if fallback.exists():
            file_path = fallback
        else:
            raise HTTPException(status_code=404, detail="PDF file not found on disk")

    try:
        pdf_doc = fitz.open(str(file_path))
        target_idx = max(0, min(len(pdf_doc) - 1, page_number - 1))
        page = pdf_doc[target_idx]
        pix = page.get_pixmap(dpi=min(300, max(72, dpi)))
        img_bytes = pix.tobytes("png")
        pdf_doc.close()
        return Response(content=img_bytes, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to render page image: {str(e)}")


@router.get("/viewer/{doc_id}/evidence-overlay", response_model=ViewerOverlayResponse)
async def get_viewer_overlay(
    doc_id: str,
    fact_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get all evidence overlay bounding boxes for a document."""
    repo = PostgresRepository(db)
    doc_uuid = uuid.UUID(doc_id)
    doc = await repo.get_document(doc_uuid)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Query all facts and their evidence for this document
    query = (
        select(Evidence, Fact)
        .join(Fact, Evidence.fact_id == Fact.id)
        .where(Evidence.document_id == doc_uuid)
    )
    if fact_id:
        query = query.where(Evidence.fact_id == uuid.UUID(fact_id))

    result = await db.execute(query)
    rows = result.all()

    overlays = []
    for ev, fact in rows:
        # Compute normalized coordinates (0.0 to 1.0)
        pw = ev.page_width if (ev.page_width and ev.page_width > 0) else 612.0
        ph = ev.page_height if (ev.page_height and ev.page_height > 0) else 792.0

        x0 = (ev.bbox_x0 / pw) if ev.bbox_x0 is not None else 0.1
        y0 = (ev.bbox_y0 / ph) if ev.bbox_y0 is not None else 0.1
        x1 = (ev.bbox_x1 / pw) if ev.bbox_x1 is not None else 0.9
        y1 = (ev.bbox_y1 / ph) if ev.bbox_y1 is not None else 0.2

        # Clamp between 0 and 1
        x0 = max(0.0, min(1.0, float(x0)))
        y0 = max(0.0, min(1.0, float(y0)))
        x1 = max(0.0, min(1.0, float(x1)))
        y1 = max(0.0, min(1.0, float(y1)))

        overlays.append(
            ViewerOverlayItem(
                fact_id=str(fact.id),
                evidence_id=str(ev.id),
                entity_name=fact.subject,
                attribute=fact.predicate,
                value_text=fact.object_value,
                page_number=ev.page_number or 1,
                block_type=ev.source_type or ev.evidence_type or "text",
                confidence=fact.confidence or 0.95,
                snippet=ev.excerpt or "",
                bbox={"x0": x0, "y0": y0, "x1": x1, "y1": y1},
            )
        )

    return ViewerOverlayResponse(
        document_id=str(doc.id),
        page_count=doc.page_count or 1,
        overlays=overlays,
    )


@router.get("/documents/{doc_id}/page/{page_number}/evidence", response_model=list[EvidenceResponse])
async def get_page_evidence(
    doc_id: str,
    page_number: int,
    db: AsyncSession = Depends(get_db),
):
    """Get all evidence on a specific page with normalized bbox coordinates."""
    repo = PostgresRepository(db)
    evidence = await repo.get_evidence_for_page(uuid.UUID(doc_id), page_number)

    return [
        EvidenceResponse(
            id=str(e.id),
            evidence_id=str(e.id),
            evidence_type=e.evidence_type,
            source_type=e.source_type,
            block_type=e.source_type or "text",
            excerpt=e.excerpt,
            snippet=e.excerpt,
            page_number=e.page_number,
            bbox_x0=e.bbox_x0 / e.page_width if e.bbox_x0 and e.page_width else None,
            bbox_y0=e.bbox_y0 / e.page_height if e.bbox_y0 and e.page_height else None,
            bbox_x1=e.bbox_x1 / e.page_width if e.bbox_x1 and e.page_width else None,
            bbox_y1=e.bbox_y1 / e.page_height if e.bbox_y1 and e.page_height else None,
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
