"""Ingestion service — orchestrates Steps 1–6 of the pipeline.

Spec §4.2:
  Step 1: SHA-256 dedup + file save
  Step 2: Text extraction (PyMuPDF)
  Step 3: Metadata extraction (regex + LLM fallback)
  Step 4: Chunking (sentence-aware sliding window)
  Step 5: Embedding generation (batch 32, unit-normalized)
  Step 6: Storage (Postgres chunks + ChromaDB vectors + paper status update)

Called by the Celery task `process_paper`.
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.vector_store import delete_chunks_by_paper, upsert_chunks
from app.models.models import Chunk as ChunkModel, Paper
from app.providers.llm_provider import get_llm_provider
from app.providers.storage_provider import get_abs_path
from app.services.chunker import chunk_pages, extract_pages
from app.services.embedding_service import embed_texts
from app.services.metadata_extractor import extract_metadata, extract_section_headings

logger = get_logger(__name__)


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def run_ingestion(paper_id: str, db: AsyncSession) -> None:
    """Run the full ingestion pipeline for a paper.

    This is the body of the Celery task. It is called with a *sync* DB
    session created by the Celery worker (see tasks.py).
    """
    logger.info("▶ Ingestion starting for paper %s", paper_id)

    # Fetch the paper row
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper:
        logger.error("Paper %s not found", paper_id)
        return

    pdf_path = get_abs_path(paper.file_path)

    try:
        # ── Step 2: Text extraction ──────────────────────────────────────────
        logger.info("  Step 2: Extracting text from PDF")
        pages = extract_pages(pdf_path)
        if not pages:
            raise ValueError("PDF contains no extractable text")

        # ── Step 3: Metadata extraction ──────────────────────────────────────
        logger.info("  Step 3: Extracting metadata")
        try:
            llm = get_llm_provider()
        except ValueError:
            llm = None  # No LLM key — use regex-only
        headings = extract_section_headings(pdf_path)
        meta = extract_metadata(pdf_path, llm_provider=llm)

        # Update paper metadata
        await db.execute(
            update(Paper)
            .where(Paper.id == paper_id)
            .values(
                title=meta.get("title"),
                authors=meta.get("authors") or [],
                publication_year=meta.get("publication_year"),
                abstract=meta.get("abstract"),
                keywords=meta.get("keywords") or [],
                doi=meta.get("doi"),
                num_pages=meta.get("num_pages"),
            )
        )
        await db.commit()

        # ── Step 4: Chunking ─────────────────────────────────────────────────
        logger.info("  Step 4: Chunking text")
        chunks = chunk_pages(pages, headings=headings)
        if not chunks:
            raise ValueError("No chunks produced from PDF")

        # ── Step 5: Embedding ────────────────────────────────────────────────
        logger.info("  Step 5: Generating embeddings for %d chunks", len(chunks))
        texts = [c.text for c in chunks]
        embeddings = embed_texts(texts)

        # ── Step 6a: Postgres chunks ─────────────────────────────────────────
        logger.info("  Step 6a: Inserting %d chunks into Postgres", len(chunks))
        chunk_ids = [str(uuid.uuid4()) for _ in chunks]
        db_chunks = []
        for chunk_id, chunk in zip(chunk_ids, chunks):
            db_chunks.append(
                ChunkModel(
                    id=chunk_id,
                    paper_id=paper_id,
                    chunk_index=chunk.chunk_index,
                    section_title=chunk.section_title,
                    page_number=chunk.page_number,
                    text=chunk.text,
                    token_count=chunk.token_count,
                )
            )
        db.add_all(db_chunks)
        await db.commit()

        # ── Step 6b: ChromaDB vectors ────────────────────────────────────────
        logger.info("  Step 6b: Upserting vectors into ChromaDB")
        paper_title = meta.get("title") or "Unknown"
        chroma_metadatas = [
            {
                "paper_id": paper_id,
                "user_id": paper.uploaded_by,          # ← user scoping
                "paper_title": paper_title,
                "page_number": chunk.page_number or 0,
                "section_title": chunk.section_title or "",
                "chunk_index": chunk.chunk_index,
                "category": paper.category or "",
            }
            for chunk in chunks
        ]
        upsert_chunks(
            ids=chunk_ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=chroma_metadatas,
        )

        # ── Step 6c: Update paper status → ready ─────────────────────────────
        await db.execute(
            update(Paper)
            .where(Paper.id == paper_id)
            .values(status="ready", title=paper_title)
        )
        await db.commit()
        logger.info("✔ Ingestion complete for paper %s (%d chunks)", paper_id, len(chunks))

    except Exception as exc:
        logger.exception("✖ Ingestion failed for paper %s: %s", paper_id, exc)
        # Cleanup partial data
        try:
            delete_chunks_by_paper(paper_id)
        except Exception:
            pass
        await db.execute(
            update(Paper)
            .where(Paper.id == paper_id)
            .values(status="failed", error_message=str(exc)[:1000])
        )
        await db.commit()
        raise
