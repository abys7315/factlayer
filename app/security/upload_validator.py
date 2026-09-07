"""Security gate for arbitrary PDF uploads."""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

try:
    import magic
except ImportError:
    magic = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

import fitz

from app.config import get_settings


@dataclass
class ValidationResult:
    """Result of upload validation."""
    is_valid: bool = True
    sanitized_filename: str = ""
    file_hash: str = ""
    page_count: int = 0
    file_size_bytes: int = 0
    mime_type: str = ""
    is_duplicate: bool = False
    rejection_reason: str | None = None
    error_message: str | None = None


class UploadValidator:
    """
    Security gate for arbitrary PDF uploads.

    Checks:
    - File size <= MAX_UPLOAD_MB
    - MIME type / header verification (magic bytes %PDF-)
    - Malformed PDF detection (attempt parse, catch exceptions)
    - Page count check (decompression bomb protection)
    - Filename sanitization (strip path traversal, special chars, limit length)
    - File hash computation (SHA-256) for deduplication
    """

    def __init__(self):
        self.settings = get_settings()

    def validate_upload(self, original_filename: str, file_data: bytes) -> ValidationResult:
        """Synchronous validation helper for unit tests and upload routes."""
        result = ValidationResult()
        result.file_size_bytes = len(file_data)

        # 0. Extension check
        if not original_filename.lower().endswith(".pdf"):
            result.is_valid = False
            result.rejection_reason = "Invalid file extension. Only .pdf files are permitted."
            result.error_message = result.rejection_reason
            return result

        # 1. File size check
        if result.file_size_bytes > self.settings.max_upload_bytes:
            result.is_valid = False
            result.rejection_reason = (
                f"File size {result.file_size_bytes / 1024 / 1024:.1f}MB "
                f"exceeds limit of {self.settings.MAX_UPLOAD_MB}MB"
            )
            result.error_message = result.rejection_reason
            return result

        if result.file_size_bytes == 0:
            result.is_valid = False
            result.rejection_reason = "Empty file"
            result.error_message = result.rejection_reason
            return result

        # 2. Magic byte / MIME check
        if file_data[:4] != b"%PDF":
            result.is_valid = False
            result.rejection_reason = "Invalid PDF magic header bytes (expected %PDF-)"
            result.error_message = result.rejection_reason
            return result

        if magic is not None:
            try:
                detected_mime = magic.from_buffer(file_data[:2048], mime=True)
                result.mime_type = detected_mime
                if detected_mime not in self.settings.ALLOWED_MIME_TYPES.split(","):
                    result.is_valid = False
                    result.rejection_reason = (
                        f"Invalid file type: {detected_mime}. "
                        f"Allowed: {self.settings.ALLOWED_MIME_TYPES}"
                    )
                    result.error_message = result.rejection_reason
                    return result
            except Exception:
                result.mime_type = "application/pdf"
        else:
            result.mime_type = "application/pdf"

        # 3. File hash
        result.file_hash = hashlib.sha256(file_data).hexdigest()

        # 4. Sanitize filename
        result.sanitized_filename = self.sanitize_filename(original_filename)

        # 5. Attempt PDF parse for malformed detection + page count
        try:
            doc = fitz.open(stream=file_data, filetype="pdf")
            result.page_count = len(doc)
            doc.close()
        except Exception as e:
            result.is_valid = False
            result.rejection_reason = f"Malformed or corrupted PDF: {str(e)[:200]}"
            result.error_message = result.rejection_reason
            return result

        # 6. Page count limit
        if result.page_count > self.settings.MAX_PAGES:
            result.is_valid = False
            result.rejection_reason = (
                f"PDF has {result.page_count} pages, "
                f"exceeding limit of {self.settings.MAX_PAGES}"
            )
            result.error_message = result.rejection_reason
            return result

        if result.page_count == 0:
            result.is_valid = False
            result.rejection_reason = "PDF has no pages"
            result.error_message = result.rejection_reason
            return result

        return result

    async def validate(self, file_data: bytes, original_filename: str) -> ValidationResult:
        """Asynchronous validation method."""
        return self.validate_upload(original_filename, file_data)

    def sanitize_filename(self, filename: str) -> str:
        """Remove path components, special characters, limit length."""
        name = Path(filename).name
        name = re.sub(r'[^\w.\-]', '_', name)
        name = re.sub(r'_+', '_', name)
        if len(name) > 200:
            stem = Path(name).stem[:190]
            suffix = Path(name).suffix
            name = stem + suffix
        if not name.lower().endswith('.pdf'):
            name += '.pdf'
        return f"{uuid.uuid4().hex[:8]}_{name}"

    async def save_file(self, file_data: bytes, sanitized_filename: str) -> Path:
        """Save validated file to upload directory."""
        upload_dir = self.settings.upload_path
        file_path = upload_dir / sanitized_filename
        file_path.write_bytes(file_data)
        return file_path
