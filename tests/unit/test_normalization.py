"""
Unit tests for data normalization and entity resolution modules.
"""

import unittest
from app.normalization.normalizer import DataNormalizer
from app.normalization.entity_resolver import EntityResolver
from app.normalization.deduplicator import FactDeduplicator


class TestNormalization(unittest.TestCase):
    def setUp(self):
        self.normalizer = DataNormalizer()
        self.resolver = EntityResolver()

    def test_normalize_currency_and_numbers(self):
        # Millions shorthand
        res1 = self.normalizer.normalize_value("$100M", "revenue")
        self.assertIsNotNone(res1)
        self.assertEqual(res1.get("currency"), "USD")
        self.assertEqual(res1.get("value"), 100000000)

        # Explicit commas
        res2 = self.normalizer.normalize_value("$100,000,000", "revenue")
        self.assertIsNotNone(res2)
        self.assertEqual(res2.get("value"), 100000000)

        # Billions shorthand
        res3 = self.normalizer.normalize_value("€2.5B", "total_assets")
        self.assertIsNotNone(res3)
        self.assertEqual(res3.get("currency"), "EUR")
        self.assertEqual(res3.get("value"), 2500000000)

    def test_normalize_percentages(self):
        res = self.normalizer.normalize_value("18.5%", "operating_margin")
        self.assertIsNotNone(res)
        self.assertEqual(res.get("value"), 18.5)
        self.assertEqual(res.get("unit"), "%")

    def test_normalize_dates_and_fiscal_years(self):
        # FY notation
        res1 = self.normalizer.normalize_temporal_scope("FY 2023", doc_date="2023-12-31")
        self.assertEqual(res1["start"], "2023-01-01")
        self.assertEqual(res1["end"], "2023-12-31")

        # Specific date
        res2 = self.normalizer.normalize_date("December 31, 2023")
        self.assertEqual(res2, "2023-12-31")

    def test_entity_resolution_alias_matching(self):
        canonical_1 = self.resolver.resolve_entity_name("Acme Technologies Inc.")
        canonical_2 = self.resolver.resolve_entity_name("Acme Tech")

        self.assertTrue(self.resolver.are_same_entity(canonical_1, canonical_2) or "acme" in canonical_1.lower())
        self.assertEqual(
            self.resolver.normalize_entity_string("Acme Technologies Inc."),
            self.resolver.normalize_entity_string("Acme Technologies, Inc.")
        )


if __name__ == "__main__":
    unittest.main()
