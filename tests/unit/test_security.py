"""
Unit tests for document upload security and sandbox validation.
"""

import unittest
from pathlib import Path
from app.security.upload_validator import UploadValidator
from app.security.processing_sandbox import ProcessingSandbox


class TestSecurity(unittest.TestCase):
    def setUp(self):
        self.validator = UploadValidator()
        self.sandbox = ProcessingSandbox()

    def test_validate_valid_pdf(self):
        sample_pdf = Path(__file__).parent.parent / "fixtures" / "synthetic" / "acme_annual_report_2023.pdf"
        if sample_pdf.exists():
            pdf_bytes = sample_pdf.read_bytes()
        else:
            pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 595 842]/Parent 2 0 R>>endobj xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000108 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n180\n%%EOF"
        result = self.validator.validate_upload("annual_report.pdf", pdf_bytes)
        self.assertTrue(result.is_valid)
        self.assertIsNone(result.error_message)

    def test_reject_invalid_extension(self):
        exe_bytes = b"%PDF-1.4\nsome content"
        result = self.validator.validate_upload("malware.exe", exe_bytes)
        self.assertFalse(result.is_valid)
        self.assertTrue("invalid" in result.error_message.lower() or "pdf" in result.error_message.lower())

    def test_reject_fake_pdf_header(self):
        fake_bytes = b"MZ\x90\x00\x03\x00\x00\x00"
        result = self.validator.validate_upload("report.pdf", fake_bytes)
        self.assertFalse(result.is_valid)
        self.assertTrue("magic" in result.error_message.lower() or "header" in result.error_message.lower() or "invalid" in result.error_message.lower())

    def test_sandbox_timeout_and_resource_limits(self):
        self.assertGreater(self.sandbox.max_memory_mb, 0)
        self.assertGreater(self.sandbox.timeout_seconds, 0)


if __name__ == "__main__":
    unittest.main()
