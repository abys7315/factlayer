"""
Unit tests for multi-hypothesis reasoning engines:
Temporal Reasoner, Context Reasoner, and Comparison Engine.
"""

import unittest
from types import SimpleNamespace
from datetime import date
from app.reasoning.temporal_reasoner import TemporalReasoner
from app.reasoning.context_reasoner import ContextReasoner
from app.reasoning.comparison_engine import ComparisonEngine
from app.models.enums import RelationshipType


def make_fact(**kwargs):
    defaults = {
        "entity_id": None,
        "subject": "Acme Technologies",
        "predicate": "revenue",
        "object_value": "100000000",
        "object_numeric": 100000000.0,
        "unit": "USD",
        "fiscal_year": "FY2023",
        "fiscal_quarter": None,
        "scope": "GAAP",
        "geography": "Global",
        "basis": "Accrual",
        "original_text": "Revenue was $100M in 2023.",
        "fact_date_exact": date(2023, 12, 31),
        "document_date": None,
        "fact_date_start": date(2023, 1, 1),
        "fact_date_end": date(2023, 12, 31),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestReasoning(unittest.TestCase):
    def setUp(self):
        self.temporal_reasoner = TemporalReasoner()
        self.context_reasoner = ContextReasoner()
        self.comparison_engine = ComparisonEngine()

    def test_temporal_supersession(self):
        fact_a = make_fact(
            predicate="ceo",
            object_value="Jane Doe",
            object_numeric=None,
            unit=None,
            original_text="CEO Jane Doe announced results.",
            fact_date_exact=date(2023, 12, 31),
        )
        fact_b = make_fact(
            predicate="ceo",
            object_value="John Smith",
            object_numeric=None,
            unit=None,
            original_text="John Smith was appointed CEO, succeeding Jane Doe.",
            fact_date_exact=date(2024, 7, 1),
        )

        res = self.comparison_engine.compare(fact_a, fact_b)
        self.assertEqual(res.relationship_type, RelationshipType.SUPERSEDES.value)
        self.assertGreater(res.confidence, 0.8)

    def test_context_reasoner_scopes(self):
        # Fact A: GAAP scope
        fact_a = make_fact(
            predicate="net_income",
            object_numeric=18000000.0,
            scope="GAAP",
        )
        # Fact B: Non-GAAP scope
        fact_b = make_fact(
            predicate="net_income",
            object_numeric=24000000.0,
            scope="Non-GAAP",
        )

        res = self.comparison_engine.compare(fact_a, fact_b)
        self.assertEqual(res.relationship_type, RelationshipType.CONTEXTUAL_DIFFERENCE.value)
        self.assertEqual(res.context_difference_type, "scope")

    def test_comparison_engine_genuine_contradiction(self):
        fact_a = make_fact(
            predicate="revenue",
            object_numeric=100000000.0,
            object_value="100000000",
            fiscal_year="FY2023",
            scope="GAAP",
        )
        fact_b = make_fact(
            predicate="revenue",
            object_numeric=85000000.0,
            object_value="85000000",
            fiscal_year="FY2023",
            scope="GAAP",
        )

        res = self.comparison_engine.compare(fact_a, fact_b)
        self.assertEqual(res.relationship_type, RelationshipType.CONTRADICTS.value)
        self.assertGreater(res.confidence, 0.8)


if __name__ == "__main__":
    unittest.main()
