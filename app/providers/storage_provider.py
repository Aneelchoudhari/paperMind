"""Storage provider — local filesystem implementation."""
from __future__ import annotations

import os
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_root = Path(settings.storage_path)


def save_paper(paper_id: str, file_bytes: bytes) -> str:
    """Save a PDF to local storage. Returns the relative storage key."""
    paper_dir = _root / "papers" / paper_id
    paper_dir.mkdir(parents=True, exist_ok=True)
    dest = paper_dir / "original.pdf"
    dest.write_bytes(file_bytes)
    key = f"papers/{paper_id}/original.pdf"
    logger.info("Saved PDF: %s (%d bytes)", key, len(file_bytes))
    return key


def load_paper(file_path: str) -> bytes:
    """Load a PDF from storage."""
    full = _root / file_path
    return full.read_bytes()


def get_abs_path(file_path: str) -> Path:
    """Return absolute path for a storage key."""
    return _root / file_path


def delete_paper(file_path: str) -> None:
    """Delete a paper file from storage."""
    full = _root / file_path
    if full.exists():
        full.unlink()
        # Try to remove the directory if empty
        try:
            full.parent.rmdir()
        except OSError:
            pass
    logger.info("Deleted storage: %s", file_path)
