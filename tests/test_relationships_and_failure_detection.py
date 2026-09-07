"""Test suite for Embeddings, Candidate Matching, 5-Factor Relationship Reasoning, and Failure Detection."""

import pytest
from backend.embeddings import embed_fact, embed_facts_batch, EmbeddingGenerator
from backend.matcher import find_candidate_pairs
from backend.relationship_classifier import classify_relationship, RelationshipClassifier
from backend.failure_detector import (
    log_failure,
    check_extraction_completeness,
    flag_low_confidence_relationships,
    get_failure_report,
    clear_failure_logs,
)


@pytest.fixture(autouse=True)
def clean_logs():
    clear_failure_logs()
    yield
    clear_failure_logs()


# ── Part 1: Embeddings ─────────────────────────────────────────────────────────

def test_embed_fact_and_batch():
    """Verify single and batch vector generation with proper 384-dimensional embeddings."""
    fact_1 = "Delhivery Total income for 9M FY2022 was ₹49,114.06 million."
    fact_2 = "Total Income stood at ₹49,114.06 million for the period ended Dec 31, 2021."
    
    emb_1 = embed_fact(fact_1)
    assert len(emb_1) == 384
    
    batch_embs = embed_facts_batch([fact_1, fact_2])
    assert len(batch_embs) == 2
    assert len(batch_embs[0]) == 384
    assert len(batch_embs[1]) == 384

    # High cosine similarity between semantically identical facts
    sim = EmbeddingGenerator.cosine_similarity(emb_1, batch_embs[1])
    assert sim >= 0.50


# ── Part 2: Candidate Matching ────────────────────────────────────────────────

def test_find_candidate_pairs():
    """Verify cosine similarity filters down pairs without making any LLM calls."""
    facts = [
        {"id": 1, "fact_text": "Delhivery Total Income for 9M FY2022 was ₹49,114.06 million."},
        {"id": 2, "fact_text": "Total Income reached ₹49,114.06 million for nine-month period ended Dec 31, 2021."},
        {"id": 3, "fact_text": "Proforma Combined Total income was ₹52,706.81 million."},
        {"id": 4, "fact_text": "Employee headcount was 450 full-time engineers in Bangalore office."},
    ]

    pairs = find_candidate_pairs(facts, threshold=0.35, top_k=5)
    assert len(pairs) >= 1

    # First pair should be the most semantically similar income statements
    top_pair = pairs[0]
    fact_a, fact_b, score = top_pair
    assert {fact_a["id"], fact_b["id"]} == {1, 2} or "Income" in fact_a["fact_text"]
    assert score >= 0.40


# ── Part 3: 5-Factor Relationship Classification (Delhivery Scenarios) ────────

def test_delhivery_corroboration_scenario():
    """Corroboration: Two total-income facts, same number, worded differently -> corroborate."""
    fact_a = {
        "fact_text": "Delhivery Total income for 9M FY2022 was ₹49,114.06 million.",
        "source_quote": "Restated Standalone Total Income: ₹49,114.06 million for the nine-month period ended December 31, 2021.",
        "time_period": "December 31, 2021",
        "value": 49114.06,
        "unit": "INR million",
        "page_number": 14,
    }
    fact_b = {
        "fact_text": "Revenue and total income stood at ₹49,114.06 million for the period ended Dec 31, 2021.",
        "source_quote": "For the nine months ended Dec 31, 2021, total revenue reached ₹49,114.06 million.",
        "time_period": "December 31, 2021",
        "value": 49114.06,
        "unit": "INR million",
        "page_number": 16,
    }

    result = classify_relationship(fact_a, fact_b)
    assert result["relationship_type"] == "corroborate"
    assert result["confidence"] >= 0.90
    assert "49,114.06" in result["explanation"] or "49114.06" in result["explanation"]


def test_delhivery_reconciliation_proforma_scenario():
    """
    Reconciliation: Proforma combined total (₹52,706.81M) vs standalone total (₹49,114.06M)
    -> expect reconcilable with reconciling_factors: ["derived_total", "scope"] (G = A + B + F).
    """
    fact_standalone = {
        "fact_text": "Standalone Total income was ₹49,114.06 million for nine-month period ended December 31, 2021.",
        "source_quote": "Restated Standalone Total Income (A): ₹49,114.06 million.",
        "time_period": "December 31, 2021",
        "value": 49114.06,
        "unit": "INR million",
        "page_number": 14,
    }
    fact_proforma = {
        "fact_text": "Proforma Combined Total income was ₹52,706.81 million for nine-month period ended December 31, 2021.",
        "source_quote": "Proforma Combined Total Income (G = A + B + F): ₹52,706.81 million reflecting Spoton acquisition.",
        "time_period": "December 31, 2021",
        "value": 52706.81,
        "unit": "INR million",
        "page_number": 15,
    }

    result = classify_relationship(fact_standalone, fact_proforma)
    assert result["relationship_type"] == "reconcilable"
    assert any(factor in result.get("reconciling_factors", []) for factor in ["derived_total", "derived_totals", "scope"])
    assert "G = A + B" in result["explanation"] or "Proforma" in result["explanation"] or "proforma" in result["explanation"]


def test_direct_contradiction_scenario():
    """Contradiction: Conflicting revenue numbers for exact same entity and period."""
    fact_a = {
        "fact_text": "Full-year FY2023 revenue was $100,000,000.",
        "source_quote": "Total Revenue for FY2023 was $100,000,000.",
        "time_period": "FY2023",
        "value": 100000000.0,
        "unit": "USD",
        "page_number": 1,
    }
    fact_b = {
        "fact_text": "Audited FY2023 revenue was revised to $85,000,000.",
        "source_quote": "Following accounting audit, FY2023 revenue was established at $85,000,000.",
        "time_period": "FY2023",
        "value": 85000000.0,
        "unit": "USD",
        "page_number": 5,
    }

    result = classify_relationship(fact_a, fact_b)
    assert result["relationship_type"] == "contradict"
    assert result["confidence"] >= 0.90


# ── Part 4: Failure Detection & Quality Auditing ──────────────────────────────

def test_central_failure_logging():
    """Verify log_failure captures error types, page, and context for auditing."""
    log_failure(
        error_type="JSON_DECODE_ERROR",
        details="Model generated truncated JSON array on chunk 4.",
        page_number=13,
        context={"chunk_preview": "{\"fact_text\": \"Incomplete..."},
    )

    report = get_failure_report()
    assert report["total_failures_logged"] == 1
    assert "JSON_DECODE_ERROR" in report["failures_by_type"]
    assert report["logs"][0]["page_number"] == 13


def test_check_extraction_completeness():
    """Verify check_extraction_completeness detects pages with high numeric density but zero/low extracted facts."""
    page_text_with_tables = """
    Financial Summary:
    Total Assets: ₹15,400.50
    Total Liabilities: ₹8,200.10
    Borrowings: ₹1,200.00
    Cash and Equivalents: ₹4,500.00
    Operating Expenses: ₹3,100.50
    Tax Expense: ₹850.00
    Net Profit: ₹1,750.00
    """
    # 0 extracted facts on a dense table page
    audit = check_extraction_completeness(page_text_with_tables, extracted_facts=[], page_number=13)
    assert audit["is_under_extracted"] is True
    assert audit["status"] == "warning"
    assert audit["numeric_tokens_count"] >= 6

    # Failure log should have recorded the warning
    report = get_failure_report()
    assert report["total_failures_logged"] >= 1
    assert "UNDER_EXTRACTION_WARNING" in report["failures_by_type"]


def test_flag_low_confidence_relationships():
    """Verify flag_low_confidence_relationships surfaces verdicts under 0.50 confidence."""
    mock_relationships = [
        {"fact_id_1": 1, "fact_id_2": 2, "relationship_type": "corroborate", "confidence": 0.98},
        {"fact_id_1": 3, "fact_id_2": 4, "relationship_type": "reconcilable", "confidence": 0.42},
    ]

    flagged = flag_low_confidence_relationships(mock_relationships, threshold=0.50)
    assert len(flagged) == 1
    assert flagged[0]["confidence"] == 0.42
    assert "below threshold" in flagged[0]["reason"]

    report = get_failure_report()
    assert "LOW_CONFIDENCE_RELATIONSHIP" in report["failures_by_type"]
