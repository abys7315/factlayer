"""Test standalone backend pipeline end-to-end."""

import sys
from pathlib import Path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from backend.db import init_db, SessionLocal, Document, Fact, Relationship
from backend.pdf_parser import PDFParser
from backend.fact_extractor import FactExtractor
from backend.embeddings import EmbeddingGenerator
from backend.matcher import FactMatcher
from backend.relationship_classifier import RelationshipClassifier

def test_pipeline():
    init_db()
    session = SessionLocal()
    parser = PDFParser()
    extractor = FactExtractor()
    emb_gen = EmbeddingGenerator()
    matcher = FactMatcher()
    rel_clf = RelationshipClassifier()

    sample_pdf = root_dir / "tests" / "fixtures" / "synthetic" / "acme_annual_report_2023.pdf"
    print(f"1. Parsing {sample_pdf.name}...")
    parsed = parser.parse_pdf(sample_pdf)
    print(f"   [OK] Page count: {parsed['page_count']}, Chunks: {len(parsed['chunks'])}")

    print("2. Extracting facts...")
    facts = []
    for chunk in parsed["chunks"]:
        extracted = extractor.extract_facts(chunk["text"], chunk["page_number"])
        for f in extracted:
            print(f"   -> Fact: {f['fact_text']} (type={f['fact_type']}, quote=\"{f['source_quote']}\")")
            facts.append(f)

    print(f"3. Extracted {len(facts)} facts successfully.")
    session.close()

if __name__ == "__main__":
    test_pipeline()
