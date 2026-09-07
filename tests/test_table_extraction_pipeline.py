"""Tests for Structural Table Extraction, Sanity Checking, and Clean Fact Extraction."""

import pytest
from pathlib import Path
import fitz

from backend.table_parser import TableParser, ExtractedTable
from backend.pdf_parser import PDFParser
from backend.fact_extractor import FactExtractor


def test_table_sanity_checks():
    """Verify sanity checker correctly identifies healthy vs broken/garbled tables."""
    parser = TableParser()

    # 1. Healthy Table
    healthy_table = [
        ["Metric", "FY 2022", "FY 2023"],
        ["Total Revenue", "$80,000,000", "$100,000,000"],
        ["Net Income", "$15,000,000", "$20,000,000"],
        ["Operating Margin", "18.5%", "20.0%"],
    ]
    is_healthy, reason = parser.check_table_sanity(healthy_table)
    assert is_healthy is True
    assert reason == "Healthy"

    # 2. Broken: Single column (just text lines detected as table)
    single_col_table = [
        ["Paragraph Header"],
        ["Some regular paragraph sentence that got confused as a row."],
    ]
    is_healthy, reason = parser.check_table_sanity(single_col_table)
    assert is_healthy is False

    # 3. Garbled: High empty cell ratio (> 65%)
    empty_cell_table = [
        ["Col1", "Col2", "Col3", "Col4"],
        ["", "", "Val", ""],
        ["", "", "", ""],
        ["Val2", "", "", ""],
    ]
    is_healthy, reason = parser.check_table_sanity(empty_cell_table)
    assert is_healthy is False

    # 4. Garbled: Mashed paragraph text inside table cell
    mashed_text_table = [
        ["Metric", "Description"],
        ["Revenue", "A" * 600],  # Long paragraph mashed into cell
    ]
    is_healthy, reason = parser.check_table_sanity(mashed_text_table)
    assert is_healthy is False


def test_matrix_to_markdown():
    """Verify conversion of raw table cells to clean Markdown."""
    parser = TableParser()
    headers = ["Metric", "FY 2022", "FY 2023"]
    rows = [
        ["Total Revenue", "$80,000,000", "$100,000,000"],
        ["Headcount", "350", "450"],
    ]
    md = parser.matrix_to_markdown(headers, rows)
    assert "| Metric | FY 2022 | FY 2023 |" in md
    assert "| --- | --- | --- |" in md
    assert "| Total Revenue | $80,000,000 | $100,000,000 |" in md
    assert "| Headcount | 350 | 450 |" in md


def test_fact_extraction_from_clean_table():
    """Verify that FactExtractor pulls clean atomic facts from clean Markdown tables."""
    extractor = FactExtractor()

    table_markdown = """### Table 1 (Page 1) [STRUCTURAL]
| Metric | FY 2022 | FY 2023 |
| --- | --- | --- |
| Total Revenue | $80,000,000 | $100,000,000 |
| GAAP Net Income | $15,000,000 | $20,000,000 |
| Full-Time Employees | 350 | 450 |
| Operating Margin | 18.5% | 20.0% |
"""

    facts = extractor._extract_deterministic(table_markdown, page_number=1)
    assert len(facts) >= 6

    # Verify Revenue facts
    rev_2022 = next((f for f in facts if "Revenue" in f["fact_text"] and f.get("time_period") == "FY2022"), None)
    assert rev_2022 is not None
    assert rev_2022["value"] == 80000000.0
    assert rev_2022["unit"] == "USD"

    rev_2023 = next((f for f in facts if "Revenue" in f["fact_text"] and f.get("time_period") == "FY2023"), None)
    assert rev_2023 is not None
    assert rev_2023["value"] == 100000000.0
    assert rev_2023["unit"] == "USD"

    # Verify Headcount facts
    hc_2023 = next((f for f in facts if "Employees" in f["fact_text"] and f.get("time_period") == "FY2023"), None)
    assert hc_2023 is not None
    assert hc_2023["value"] == 450.0


def test_pdf_parser_with_table(tmp_path: Path):
    """Generate a test PDF with text and table, and verify end-to-end PDF parsing and table formatting."""
    pdf_file = tmp_path / "sample_financial_report.pdf"

    # Create synthetic PDF with table text
    doc = fitz.open()
    page = doc.new_page()

    text_content = """Acme Technologies Annual Report 2023
The company experienced strong financial momentum in fiscal year 2023.

Financial Highlights:
| Metric | FY 2022 | FY 2023 |
| Total Revenue | $80,000,000 | $100,000,000 |
| Net Income | $15,000,000 | $20,000,000 |
"""
    page.insert_text((50, 50), text_content, fontsize=11)
    doc.save(str(pdf_file))
    doc.close()

    parser = PDFParser()
    result = parser.parse_pdf(pdf_file)

    assert result["page_count"] == 1
    assert len(result["chunks"]) >= 1
    assert "Acme Technologies" in result["full_text"]


def test_two_pass_and_table_coverage_backfill():
    """Verify that table coverage validation detects under-extracted table cells and backfills them."""
    extractor = FactExtractor(enable_two_pass=True)

    text_with_table = """### Proforma Summary Financials
The following table sets out proforma financials assuming the acquisition completed on Jan 1, 2023.

| Line Item | Restated (A) | Spoton (B) | Adjustment (C) | Proforma (D) |
| --- | --- | --- | --- | --- |
| Revenue from contracts | $48,105 | $7,575 | ($3,974) | $51,706 |
| Freight and handling costs | $38,400 | $5,200 | $0 | $43,600 |
| Employee benefits expense | $5,800 | $1,100 | ($200) | $6,700 |
| EBITDA | $3,905 | $1,275 | ($3,774) | $1,406 |

* Footnote 1: Adjustment (C) reflects intercompany eliminations.
"""

    # Simulate extraction where Pass 1 only extracted top totals
    mock_pass1_facts = [
        {
            "fact_text": "Proforma Revenue from contracts is $51,706.",
            "fact_type": "financial",
            "value": 51706.0,
            "unit": "USD",
            "time_period": "2023",
            "source_quote": "| Revenue from contracts | $48,105 | $7,575 | ($3,974) | $51,706 |",
            "page_number": 1,
        }
    ]

    # Validate backfilling
    backfilled = extractor._validate_and_backfill_tables(mock_pass1_facts, text_with_table, page_number=1)
    
    # All other rows & column intersections should be recovered!
    assert len(backfilled) >= 10
    
    # Check that negative adjustment was parsed correctly as negative float
    adj_fact = next((f for f in backfilled if "Revenue from contracts" in f["fact_text"] and "Adjustment" in f["fact_text"]), None)
    assert adj_fact is not None
    assert adj_fact["value"] == -3974.0

    # Test deduplication
    combined = mock_pass1_facts + backfilled
    deduped = extractor._deduplicate_facts(combined)
    assert len(deduped) == len(combined)  # No duplicates created


def test_numeric_parentheses_and_crore_multipliers():
    """Verify parsing of negative parentheses, crore, lakh, million, and billion strings."""
    extractor = FactExtractor()
    assert extractor._parse_numeric("(3,973.94)") == -3973.94
    assert extractor._parse_numeric("($50.5M)") == -50500000.0
    assert extractor._parse_numeric("₹1,250 crore") == 12500000000.0
    assert extractor._parse_numeric("₹45 lakh") == 4500000.0
    assert extractor._parse_numeric("$100 billion") == 100000000000.0
    assert extractor._parse_numeric("-18.5%") == -18.5


def test_page_16_balance_sheet_extraction_isolation():
    """Targeted test: Verify fact extraction on Page 16 (Delhivery balance-sheet page) in isolation."""
    extractor = FactExtractor(enable_two_pass=False)

    page_16_text = """### Page 16 - Balance Sheet Highlights
(in ₹ million, unless otherwise stated)

| Particulars | As at December 31, 2021 | As at December 31, 2020 | As at March 31, 2021 | As at March 31, 2020 |
| --- | --- | --- | --- | --- |
| Total equity | 59,798.47 | 29,148.37 | 28,367.97 | 31,704.06 |
| Borrowings | 1,005.28 | 1,329.84 | 1,316.09 | 998.02 |
| Lease liabilities | 6,912.95 | 6,563.72 | 6,538.44 | 3,870.65 |
| Total non-current liabilities | 9,059.75 | 8,108.14 | 8,073.69 | 5,035.89 |
"""

    facts = extractor.extract_facts(page_16_text, page_number=16)

    assert len(facts) >= 12
    # Verify exact Page 16 attribution
    for f in facts:
        assert f["page_number"] == 16
        assert "QR Code" not in f["fact_text"]
        assert "DOCUMENT" not in f["fact_text"]
        assert "prospectus" not in f["fact_text"].lower()

    # Verify substantive balance sheet facts
    eq_fact = next((f for f in facts if "Total equity" in f["fact_text"] and ("December 31, 2021" in str(f.get("time_period", "")) or "December 31, 2021" in f["fact_text"])), None)
    assert eq_fact is not None
    assert eq_fact["value"] == 59798.47
    assert eq_fact["unit"] in ("INR million", "INR", "million")
    assert eq_fact["page_number"] == 16

    borrow_fact = next((f for f in facts if "Borrowings" in f["fact_text"] and ("December 31, 2021" in str(f.get("time_period", "")) or "December 31, 2021" in f["fact_text"])), None)
    assert borrow_fact is not None
    assert borrow_fact["value"] == 1005.28
    assert borrow_fact["page_number"] == 16


def test_bbox_at_extraction_time(tmp_path: Path):
    """Verify that extract_page_chunks_with_bbox captures word/line coordinates and groups into merged bboxes."""
    from backend.pdf_parser import extract_page_chunks_with_bbox, group_chunks_into_blocks
    
    pdf_file = tmp_path / "bbox_test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Delhivery Limited Financial Statements", fontsize=12)
    page.insert_text((72, 120), "Total Equity was INR 59,798.47 million as at December 31, 2021.", fontsize=10)
    page.insert_text((72, 250), "Non-current liabilities reached INR 9,059.75 million.", fontsize=10)
    doc.save(str(pdf_file))
    doc.close()

    chunks = extract_page_chunks_with_bbox(str(pdf_file), page_num=1)
    assert len(chunks) >= 3
    for c in chunks:
        assert "bbox" in c
        assert len(c["bbox"]) == 4
        assert c["page_number"] == 1
        assert c["bbox"][2] > c["bbox"][0]  # x1 > x0
        assert c["bbox"][3] > c["bbox"][1]  # y1 > y0

    blocks = group_chunks_into_blocks(chunks, y_gap_threshold=25.0)
    assert len(blocks) >= 2  # top paragraph and bottom paragraph separated by gap
    assert "Delhivery Limited" in blocks[0]["text"]
    assert "Non-current liabilities" in blocks[-1]["text"]
    # Check that merged bbox spans lines
    assert blocks[0]["bbox"][3] >= 120.0


def test_table_artifact_cleaner():
    """Verify that strip_table_artifacts and clean_table_headers remove placeholder Column_N labels."""
    from backend.table_cleaner import strip_table_artifacts, clean_table_headers

    raw_text = "Revenue in (Column_16) for FY23 was $100M (Unnamed: 3)."
    cleaned = strip_table_artifacts(raw_text)
    assert "Column_16" not in cleaned
    assert "Unnamed: 3" not in cleaned
    assert "$100M" in cleaned

    headers = ["Metric", "Column_1", "Unnamed: 2", "FY 2023", "Field_4"]
    clean_h = clean_table_headers(headers)
    assert clean_h[0] == "Metric"
    assert clean_h[1] == "[unlabeled column — infer from context]"
    assert clean_h[2] == "[unlabeled column — infer from context]"
    assert clean_h[3] == "FY 2023"
    assert clean_h[4] == "[unlabeled column — infer from context]"


def test_fact_type_reasoning_and_bbox_propagation():
    """Verify that fact_type_reasoning is present and justified, and bbox is propagated."""
    from backend.fact_extractor import FactExtractor, extract_facts_from_block

    extractor = FactExtractor(enable_two_pass=False)
    block = {
        "text": "Acme Technologies Inc. achieved total revenue of $100,000,000 for fiscal year 2023.",
        "bbox": (50.0, 100.0, 450.0, 125.0),
        "page_number": 1,
    }

    # Test standalone extraction with bbox
    facts = extractor.extract_facts(block["text"], page_number=1, bbox=block["bbox"])
    assert len(facts) >= 1
    for f in facts:
        assert "fact_type_reasoning" in f
        assert len(f["fact_type_reasoning"]) > 5
        assert f["bbox"] == (50.0, 100.0, 450.0, 125.0)

    # Test extract_facts_from_block fallback
    block_facts = extract_facts_from_block(None, block)
    assert len(block_facts) >= 1
    assert block_facts[0]["bbox"] == (50.0, 100.0, 450.0, 125.0)
    assert "fact_type_reasoning" in block_facts[0]



