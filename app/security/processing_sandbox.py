"""Isolated processing directory management with timeouts."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from contextlib import asynccontextmanager

from app.config import get_settings


class ProcessingSandbox:
    """
    Isolated processing directory management.

    - Creates unique temp directory per document processing job
    - Ensures cleanup on completion or failure
    - Never executes embedded PDF content (JavaScript, actions)
    """

    def __init__(self):
        self.settings = get_settings()
        self.max_memory_mb = getattr(self.settings, "MAX_UPLOAD_MB", 100)
        self.timeout_seconds = getattr(self.settings, "MAX_PROCESSING_SECONDS", 600)

    @asynccontextmanager
    async def create_sandbox(self, document_id: str):
        """Create and manage an isolated processing directory."""
        sandbox_dir = self.settings.processing_path / f"proc_{document_id}_{uuid.uuid4().hex[:8]}"
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        try:
            yield sandbox_dir
        finally:
            # Cleanup
            if sandbox_dir.exists():
                shutil.rmtree(sandbox_dir, ignore_errors=True)

    def get_temp_path(self, sandbox_dir: Path, filename: str) -> Path:
        """Get a safe temporary file path within the sandbox."""
        # Prevent path traversal
        safe_name = Path(filename).name
        return sandbox_dir / safe_name
