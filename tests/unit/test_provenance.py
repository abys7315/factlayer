"""
Unit tests for evidence provenance tracking, bounding-box coordinate verification, and validation.
"""

import unittest
from app.provenance.tracker import ProvenanceTracker
from app.provenance.validator import ProvenanceValidator


class TestProvenance(unittest.TestCase):
    def setUp(self):
        self.tracker = ProvenanceTracker()
        self.validator = ProvenanceValidator()

    def test_provenance_bbox_normalization(self):
        raw_bbox = {"x0": 50, "y0": 100, "x1": 500, "y1": 150}
        page_width = 595.0
        page_height = 842.0

        norm_bbox = self.tracker.normalize_bbox(raw_bbox, page_width, page_height)
        self.assertTrue(0.0 <= norm_bbox["x0"] <= 1.0)
        self.assertTrue(0.0 <= norm_bbox["y0"] <= 1.0)
        self.assertTrue(0.0 <= norm_bbox["x1"] <= 1.0)
        self.assertTrue(0.0 <= norm_bbox["y1"] <= 1.0)
        self.assertGreater(norm_bbox["x1"], norm_bbox["x0"])
        self.assertGreater(norm_bbox["y1"], norm_bbox["y0"])

    def test_provenance_validator_snippet_grounding(self):
        page_text = "Acme Technologies Inc. achieved total revenue of $100M in fiscal year 2023."
        snippet = "total revenue of $100M"

        validation = self.validator.validate_grounding(page_text, snippet)
        self.assertTrue(validation.is_grounded)
        self.assertGreaterEqual(validation.char_offset_start, 0)
        self.assertGreater(validation.char_offset_end, validation.char_offset_start)


if __name__ == "__main__":
    unittest.main()
