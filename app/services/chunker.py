"""Sentence-aware sliding window chunker.

Spec §4.2 Step 4:
  - Chunk size: 512 tokens (embedding model tokenizer)
  - Overlap:    64 tokens (~12.5%)
  - Split by sentences (pysbd preferred over nltk for academic text)
  - Attach page_number from first sentence in chunk
  - Attach section_title from nearest preceding heading
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Tokeniser (reuse the embedding model's tokenizer for accurate counts) ─────
_tokenizer = None


def _get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        from transformers import AutoTokenizer
        _tokenizer = AutoTokenizer.from_pretrained(settings.embedding_model)
    return _tokenizer


def _token_count(text: str) -> int:
    return len(_get_tokenizer().encode(text, add_special_tokens=False))


# ── Sentence splitter ────────────────────────────────────────────────────────

def _split_sentences(text: str) -> list[str]:
    try:
        import pysbd
        seg = pysbd.Segmenter(language="en", clean=True)
        return seg.segment(text)
    except Exception:
        import nltk
        try:
            return nltk.sent_tokenize(text)
        except Exception:
            # Fallback: split on period + space
            return re.split(r"(?<=[.!?])\s+", text)


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Chunk:
    chunk_index: int
    text: str
    token_count: int
    page_number: Optional[int] = None
    section_title: Optional[str] = None


# ── Public API ────────────────────────────────────────────────────────────────

MAX_TOKENS = 512
OVERLAP_TOKENS = 64


def extract_pages(pdf_path: str | Path) -> list[tuple[int, str]]:
    """Return list of (page_number_1indexed, page_text) from a PDF."""
    doc = fitz.open(str(pdf_path))
    pages = []
    try:
        for pno in range(doc.page_count):
            text = doc[pno].get_text("text").strip()
            if text:
                pages.append((pno + 1, text))
    finally:
        doc.close()
    return pages


def chunk_pages(
    pages: list[tuple[int, str]],
    headings: list[dict] | None = None,
) -> list[Chunk]:
    """Chunk a list of (page_number, text) tuples into sliding-window chunks.

    Args:
        pages: List of (page_number, text) tuples from extract_pages().
        headings: Optional list of {heading, page_number} dicts for
                  section title annotation.
    Returns:
        List of Chunk objects with all metadata populated.
    """
    # Build a flat list of (sentence, page_number)
    sentence_pages: list[tuple[str, int]] = []
    for pno, text in pages:
        sents = _split_sentences(text)
        for s in sents:
            s = s.strip()
            if s:
                sentence_pages.append((s, pno))

    if not sentence_pages:
        return []

    chunks: list[Chunk] = []
    i = 0

    while i < len(sentence_pages):
        # Greedily accumulate sentences until we exceed MAX_TOKENS
        window: list[tuple[str, int]] = []
        total_tokens = 0
        j = i
        while j < len(sentence_pages):
            sent, pno = sentence_pages[j]
            tc = _token_count(sent)
            if total_tokens + tc > MAX_TOKENS and window:
                break
            window.append((sent, pno))
            total_tokens += tc
            j += 1

        if not window:
            # Single sentence exceeds limit — include it anyway
            window = [sentence_pages[i]]
            j = i + 1

        chunk_text = " ".join(s for s, _ in window)
        chunk_page = window[0][1]
        section = _nearest_heading(chunk_page, headings)

        chunks.append(
            Chunk(
                chunk_index=len(chunks),
                text=chunk_text,
                token_count=_token_count(chunk_text),
                page_number=chunk_page,
                section_title=section,
            )
        )

        # Walk back OVERLAP_TOKENS from end of window
        overlap_tokens = 0
        back = len(window) - 1
        while back > 0:
            overlap_tokens += _token_count(window[back][0])
            if overlap_tokens >= OVERLAP_TOKENS:
                break
            back -= 1

        # Advance i to start of overlap
        if back <= 0 or j <= i:
            i = j
        else:
            i = i + back

    logger.info("Chunked into %d chunks (max_tokens=%d, overlap=%d)",
                len(chunks), MAX_TOKENS, OVERLAP_TOKENS)
    return chunks


# ── Helper ────────────────────────────────────────────────────────────────────

def _nearest_heading(page_number: int, headings: list[dict] | None) -> str | None:
    if not headings:
        return None
    nearest = None
    for h in headings:
        if h["page_number"] <= page_number:
            nearest = h["heading"]
    return nearest
