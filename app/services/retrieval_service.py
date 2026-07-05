"""Retrieval service — BM25 (Postgres FTS) + Semantic (ChromaDB) + RRF.

Spec §5:
  §5.1 BM25 via Postgres tsvector / ts_rank_cd (top-50)
  §5.2 Semantic via ChromaDB cosine similarity (top-50)
  §5.3 Hybrid fusion: Reciprocal Rank Fusion k=60 → top-20
  §5.4 Cross-encoder re-ranking → top-5 final
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.vector_store import query_similar
from app.services.embedding_service import embed_query

logger = get_logger(__name__)


# ── BM25 via Postgres FTS ─────────────────────────────────────────────────────

async def keyword_search(
    query: str,
    db: AsyncSession,
    top_k: int = 50,
    filters: Optional[dict] = None,
    user_id: Optional[str] = None,
) -> list[dict]:
    """Full-text search using Postgres tsvector and ts_rank_cd."""
    sql = """
        SELECT
            c.id,
            c.paper_id,
            c.text,
            c.page_number,
            c.section_title,
            c.chunk_index,
            p.title AS paper_title,
            p.category,
            ts_rank_cd(to_tsvector('english', COALESCE(c.text, '')), plainto_tsquery('english', :query)) AS score
        FROM chunks c
        JOIN papers p ON c.paper_id = p.id
        WHERE to_tsvector('english', COALESCE(c.text, '')) @@ plainto_tsquery('english', :query)
          AND p.status = 'ready'
    """
    params: dict = {"query": query}

    if user_id:
        sql += " AND p.uploaded_by = :user_id"
        params["user_id"] = user_id

    if filters:
        if filters.get("category"):
            sql += " AND p.category = :category"
            params["category"] = filters["category"]
        if filters.get("year_min"):
            sql += " AND p.publication_year >= :year_min"
            params["year_min"] = filters["year_min"]
        if filters.get("year_max"):
            sql += " AND p.publication_year <= :year_max"
            params["year_max"] = filters["year_max"]

    sql += " ORDER BY score DESC LIMIT :limit"
    params["limit"] = top_k

    rows = (await db.execute(text(sql), params)).mappings().all()
    return [dict(r) for r in rows]


# ── Semantic search via ChromaDB ─────────────────────────────────────────────

async def semantic_search(
    query: str,
    top_k: int = 50,
    filters: Optional[dict] = None,
    user_id: Optional[str] = None,
) -> list[dict]:
    """Vector similarity search via ChromaDB."""
    q_emb = embed_query(query)
    where = _build_chroma_where(filters, user_id=user_id)
    results = query_similar(q_emb, n_results=top_k, where=where)

    items = []
    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for cid, doc, meta, dist in zip(ids, docs, metas, distances):
        items.append(
            {
                "id": cid,
                "paper_id": meta.get("paper_id", ""),
                "text": doc,
                "page_number": meta.get("page_number"),
                "section_title": meta.get("section_title"),
                "chunk_index": meta.get("chunk_index"),
                "paper_title": meta.get("paper_title"),
                "category": meta.get("category"),
                "score": float(1 - dist),  # convert distance → similarity
            }
        )
    return items


def _build_chroma_where(
    filters: Optional[dict],
    user_id: Optional[str] = None,
) -> Optional[dict]:
    conditions = []
    if user_id:
        conditions.append({"user_id": {"$eq": user_id}})
    if filters:
        if filters.get("category"):
            conditions.append({"category": {"$eq": filters["category"]}})
    if not conditions:
        return None
    return {"$and": conditions} if len(conditions) > 1 else conditions[0]


# ── Reciprocal Rank Fusion ────────────────────────────────────────────────────

def reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    k: int = 60,
    top_n: int = 20,
) -> list[str]:
    """Fuse multiple ranked lists into one via RRF.

    Args:
        ranked_lists: Each list is an ordered list of chunk IDs (best first).
        k: RRF damping constant (60 per spec).
        top_n: Number of results to return.
    Returns:
        Ordered list of chunk IDs by descending RRF score.
    """
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, chunk_id in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda c: scores[c], reverse=True)[:top_n]


# ── Hybrid search (public entry point) ───────────────────────────────────────

async def hybrid_search(
    query: str,
    db: AsyncSession,
    mode: str = "hybrid",
    top_k: int = 50,
    filters: Optional[dict] = None,
    user_id: Optional[str] = None,
) -> tuple[list[dict], dict[str, dict]]:
    """Run keyword / semantic / hybrid search scoped to a specific user.

    Returns:
        (ranked_chunk_ids_after_RRF, chunk_details_map)
    """
    kw_results: list[dict] = []
    sem_results: list[dict] = []

    if mode in ("keyword", "hybrid"):
        kw_results = await keyword_search(query, db, top_k=top_k, filters=filters, user_id=user_id)

    if mode in ("semantic", "hybrid"):
        sem_results = await semantic_search(query, top_k=top_k, filters=filters, user_id=user_id)

    # Build chunk detail map (id → detail dict)
    chunk_map: dict[str, dict] = {}
    for r in kw_results:
        chunk_map[r["id"]] = r
    for r in sem_results:
        chunk_map.setdefault(r["id"], r)

    if mode == "keyword":
        ranked_ids = [r["id"] for r in kw_results]
    elif mode == "semantic":
        ranked_ids = [r["id"] for r in sem_results]
    else:
        kw_ids = [r["id"] for r in kw_results]
        sem_ids = [r["id"] for r in sem_results]
        ranked_ids = reciprocal_rank_fusion(
            [kw_ids, sem_ids],
            k=settings.rrf_k,
            top_n=settings.rrf_top_n,
        )

    logger.info(
        "Search: mode=%s user=%s query='%s' → %d results (kw=%d, sem=%d)",
        mode, user_id, query, len(ranked_ids), len(kw_results), len(sem_results),
    )
    return ranked_ids, chunk_map
