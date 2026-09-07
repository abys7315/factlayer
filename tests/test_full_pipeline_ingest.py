"""Test full ingestion pipeline on synthetic PDFs."""

import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import asyncio
from app.workers.pipeline import IngestionPipeline
from app.storage.postgres_repository import PostgresRepository
from app.models.database import get_session_factory
from app.models import Document, ProcessingStatus
from app.security.upload_validator import UploadValidator


async def main():
    session_factory = get_session_factory()
    validator = UploadValidator()
    pipeline = IngestionPipeline()

    synthetic_dir = root_dir / "tests" / "fixtures" / "synthetic"
    pdf_files = list(synthetic_dir.glob("*.pdf"))
    print(f"Found {len(pdf_files)} synthetic PDF files to ingest.")

    for pdf_path in pdf_files:
        with open(pdf_path, "rb") as f:
            file_data = f.read()

        val_res = await validator.validate(file_data, pdf_path.name)
        saved_path = await validator.save_file(file_data, val_res.sanitized_filename)

        async with session_factory() as session:
            repo = PostgresRepository(session)
            existing = await repo.get_document_by_hash(val_res.file_hash)
            if existing:
                doc_id = str(existing.id)
            else:
                doc = await repo.create_document(
                    filename=val_res.sanitized_filename,
                    original_filename=pdf_path.name,
                    file_hash=val_res.file_hash,
                    file_size_bytes=val_res.file_size_bytes,
                    page_count=val_res.page_count,
                    mime_type=val_res.mime_type,
                    status=ProcessingStatus.QUEUED.value,
                )
                await session.commit()
                doc_id = str(doc.id)

        print(f"-> Processing {pdf_path.name} (id={doc_id})...")
        metrics = await pipeline.process_document(doc_id, str(saved_path))
        print(f"   [DONE] Facts: {metrics['facts_extracted']}, Rels: {metrics['relationships_created']}, Stages: {len(metrics['stages_completed'])}/11")

    # Summary
    async with session_factory() as session:
        repo = PostgresRepository(session)
        total_facts = await repo.count_facts()
        total_rels = await repo.count_relationships()
        contradictions = await repo.count_relationships("CONTRADICTS")
        supersedes = await repo.count_relationships("SUPERSEDES")
        print("\n" + "=" * 50)
        print(f"TOTAL FACTS EXTRACTED: {total_facts}")
        print(f"TOTAL RELATIONSHIPS CREATED: {total_rels}")
        print(f"TOTAL CONTRADICTIONS: {contradictions}")
        print(f"TOTAL SUPERSEDED FACTS: {supersedes}")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
