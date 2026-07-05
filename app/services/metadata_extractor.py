"""Metadata extractor — hybrid rule-based + LLM fallback.

Step 3 of the ingestion pipeline (spec §4.2 Step 3):
  1. Title: largest-font text block on page 1
  2. Authors: regex for comma/and-separated names below title
  3. Abstract: between 'abstract' heading and next heading
  4. Year: regex \\b(19|20)\\d{2}\\b
  5. DOI: regex 10\\.\\d{4,9}/...
  6. Keywords: after 'index terms' / 'keywords' heading
  LLM fallback on confidence failure.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Regexes ──────────────────────────────────────────────────────────────────
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")
_ABSTRACT_HEADING_RE = re.compile(r"^abstract$", re.IGNORECASE)
_KEYWORDS_HEADING_RE = re.compile(r"^(index\s*terms|keywords)$", re.IGNORECASE)
_SECTION_NUM_RE = re.compile(r"^\d+(\.\d+)*\s+[A-Z]")
_HEADING_RE = re.compile(
    r"^(\d+(\.\d+)*\.?\s+)?[A-Z][A-Za-z\s]{2,60}$"
)


# ── Public API ────────────────────────────────────────────────────────────────


def extract_metadata(pdf_path: str | Path, llm_provider=None) -> dict[str, Any]:
    """Extract bibliographic metadata from a PDF.

    Returns a dict with keys: title, authors, publication_year, abstract,
    keywords, doi, journal_or_venue (always present, may be None).
    """
    doc = fitz.open(str(pdf_path))
    try:
        # Gather text + font-size data from first 3 pages
        page_blocks = []
        for pno in range(min(3, doc.page_count)):
            page = doc[pno]
            d = page.get_text("dict")
            page_blocks.append((pno, d))

        title = _extract_title(page_blocks)
        authors = _extract_authors(page_blocks, title)
        abstract = _extract_abstract(doc)
        year = _extract_year(page_blocks)
        doi = _extract_doi(page_blocks)
        keywords = _extract_keywords(doc)

        # Assess confidence — if title and authors missing, use LLM
        missing = not title or not authors
        if missing and llm_provider:
            logger.info("Falling back to LLM for metadata extraction")
            first_text = _first_text(doc, max_chars=2000)
            llm_meta = _llm_extract(first_text, llm_provider)
            title = title or llm_meta.get("title")
            authors = authors or llm_meta.get("authors") or []
            abstract = abstract or llm_meta.get("abstract")
            year = year or llm_meta.get("publication_year")
            doi = doi or llm_meta.get("doi")
            keywords = keywords or llm_meta.get("keywords") or []

        return {
            "title": title,
            "authors": authors or [],
            "publication_year": year,
            "abstract": abstract,
            "keywords": keywords or [],
            "doi": doi,
            "journal_or_venue": None,
            "num_pages": doc.page_count,
        }
    finally:
        doc.close()


def extract_section_headings(pdf_path: str | Path) -> list[dict]:
    """Return a list of {heading, page_number} for section heading detection."""
    doc = fitz.open(str(pdf_path))
    headings = []
    try:
        body_font_size = _estimate_body_font(doc)
        for pno in range(doc.page_count):
            page = doc[pno]
            blocks = page.get_text("dict")["blocks"]
            for blk in blocks:
                for line in blk.get("lines", []):
                    for span in line.get("spans", []):
                        txt = span["text"].strip()
                        size = span["size"]
                        flags = span.get("flags", 0)
                        is_bold = bool(flags & 2**4)
                        if (
                            txt
                            and (size > body_font_size + 0.5 or is_bold)
                            and _HEADING_RE.match(txt)
                            and len(txt) < 80
                        ):
                            headings.append({"heading": txt, "page_number": pno + 1})
    finally:
        doc.close()
    return headings


# ── Private helpers ──────────────────────────────────────────────────────────


def _extract_title(page_blocks: list) -> str | None:
    """Largest font-size text on page 1."""
    best_txt, best_size = None, 0.0
    pno, d = page_blocks[0]
    for blk in d.get("blocks", []):
        for line in blk.get("lines", []):
            for span in line.get("spans", []):
                txt = span["text"].strip()
                size = span["size"]
                if txt and size > best_size and len(txt) > 5:
                    best_size = size
                    best_txt = txt
    return best_txt


def _extract_authors(page_blocks: list, title: str | None) -> list[str] | None:
    """Text block just below the title on page 1."""
    pno, d = page_blocks[0]
    spans_sorted = []
    for blk in d.get("blocks", []):
        for line in blk.get("lines", []):
            for span in line.get("spans", []):
                spans_sorted.append(span)
    spans_sorted.sort(key=lambda s: s.get("origin", (0, 0))[1])

    found_title = False
    for span in spans_sorted:
        txt = span["text"].strip()
        if title and title in txt:
            found_title = True
            continue
        if found_title and txt:
            parts = re.split(r",\s*|\s+and\s+", txt)
            parts = [p.strip() for p in parts if len(p.strip()) > 2]
            if parts:
                return parts
    return None


def _extract_abstract(doc: fitz.Document) -> str | None:
    """Text between 'Abstract' heading and next heading."""
    in_abstract = False
    done = False
    lines_buf: list[str] = []

    for pno in range(min(5, doc.page_count)):
        if done:
            break
        page = doc[pno]
        text = page.get_text("text")
        for line in text.splitlines():
            stripped = line.strip()
            if _ABSTRACT_HEADING_RE.match(stripped):
                in_abstract = True
                continue
            if in_abstract:
                if _HEADING_RE.match(stripped) and stripped.lower() not in (
                    "abstract",
                    "introduction",
                ):
                    done = True
                    break
                lines_buf.append(stripped)

    txt = " ".join(lines_buf).strip()
    return txt if len(txt) > 50 else None


def _extract_year(page_blocks: list) -> int | None:
    for pno, d in page_blocks:
        for blk in d.get("blocks", []):
            for line in blk.get("lines", []):
                for span in line.get("spans", []):
                    m = _YEAR_RE.search(span["text"])
                    if m:
                        return int(m.group())
    return None


def _extract_doi(page_blocks: list) -> str | None:
    for pno, d in page_blocks:
        for blk in d.get("blocks", []):
            for line in blk.get("lines", []):
                for span in line.get("spans", []):
                    m = _DOI_RE.search(span["text"])
                    if m:
                        return m.group()
    return None


def _extract_keywords(doc: fitz.Document) -> list[str] | None:
    for pno in range(min(5, doc.page_count)):
        page = doc[pno]
        text = page.get_text("text")
        for i, line in enumerate(text.splitlines()):
            if _KEYWORDS_HEADING_RE.match(line.strip()):
                # Next non-empty line(s) are keywords
                kw_lines = []
                for kline in text.splitlines()[i + 1 : i + 5]:
                    if kline.strip():
                        kw_lines.append(kline.strip())
                    else:
                        break
                if kw_lines:
                    raw = " ".join(kw_lines)
                    parts = re.split(r"[,;·•]\s*", raw)
                    return [p.strip() for p in parts if p.strip()]
    return None


def _first_text(doc: fitz.Document, max_chars: int = 2000) -> str:
    buf: list[str] = []
    total = 0
    for pno in range(min(3, doc.page_count)):
        t = doc[pno].get_text("text")
        buf.append(t)
        total += len(t)
        if total >= max_chars:
            break
    return " ".join(buf)[:max_chars]


def _estimate_body_font(doc: fitz.Document) -> float:
    sizes: list[float] = []
    for pno in range(min(3, doc.page_count)):
        page = doc[pno]
        for blk in page.get_text("dict")["blocks"]:
            for line in blk.get("lines", []):
                for span in line.get("spans", []):
                    sizes.append(span["size"])
    if not sizes:
        return 10.0
    sizes.sort()
    return sizes[len(sizes) // 2]  # median


def _llm_extract(first_text: str, llm_provider) -> dict:
    system = (
        "You extract bibliographic metadata from academic paper text. "
        "Return ONLY valid JSON with keys: title, authors (array of strings), "
        "publication_year (int or null), abstract (string or null), "
        "keywords (array of strings or empty array), doi (string or null). "
        "Do not invent values you cannot find in the text. Use null / [] when unsure."
    )
    try:
        return llm_provider.complete_json(system, first_text)
    except Exception as e:
        logger.warning("LLM metadata extraction failed: %s", e)
        return {}
