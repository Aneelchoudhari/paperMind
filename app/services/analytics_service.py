"""Analytics service — aggregated dashboard stats, Redis-cached per user."""
from __future__ import annotations

import json
from collections import Counter
from typing import Optional

import redis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.models import Chunk, Paper, SearchHistory

logger = get_logger(__name__)

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def get_analytics_overview(db: AsyncSession, user_id: Optional[str] = None) -> dict:
    """Fetch analytics overview for a user, Redis-cached per user for 5 minutes."""
    r = _get_redis()
    cache_key = f"papermind:analytics:overview:{user_id or 'global'}"
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)

    data = await _compute_overview(db, user_id=user_id)
    r.setex(cache_key, settings.analytics_cache_ttl, json.dumps(data))
    return data


async def _compute_overview(db: AsyncSession, user_id: Optional[str] = None) -> dict:
    # ── Total papers (scoped to user) ──────────────────────────────────────────
    papers_query = select(func.count()).where(Paper.status == "ready")
    if user_id:
        papers_query = papers_query.where(Paper.uploaded_by == user_id)
    total_papers = (await db.execute(papers_query)).scalar_one()

    # ── Total chunks (scoped via JOIN to user's papers) ────────────────────────
    if user_id:
        chunks_result = await db.execute(
            text("SELECT COUNT(*) FROM chunks c JOIN papers p ON c.paper_id = p.id WHERE p.uploaded_by = :uid"),
            {"uid": user_id},
        )
        total_chunks = chunks_result.scalar_one()
    else:
        total_chunks = (await db.execute(select(func.count()).select_from(Chunk))).scalar_one()

    # ── By category ───────────────────────────────────────────────────────────
    cat_query = (
        select(Paper.category, func.count().label("count"))
        .where(Paper.status == "ready")
        .group_by(Paper.category)
        .order_by(func.count().desc())
    )
    if user_id:
        cat_query = cat_query.where(Paper.uploaded_by == user_id)
    cat_rows = (await db.execute(cat_query)).all()
    by_category = [{"category": r.category, "count": r.count} for r in cat_rows]

    # ── By year ───────────────────────────────────────────────────────────────
    year_query = (
        select(Paper.publication_year, func.count().label("count"))
        .where(Paper.status == "ready")
        .group_by(Paper.publication_year)
        .order_by(Paper.publication_year)
    )
    if user_id:
        year_query = year_query.where(Paper.uploaded_by == user_id)
    year_rows = (await db.execute(year_query)).all()
    by_year = [{"year": r.publication_year, "count": r.count} for r in year_rows]

    # ── Top authors ───────────────────────────────────────────────────────────
    author_sql = """
        SELECT unnest(authors) AS author, count(*) AS cnt
        FROM papers
        WHERE status = 'ready' AND authors IS NOT NULL
        {user_filter}
        GROUP BY author
        ORDER BY cnt DESC
        LIMIT 10
    """
    user_filter = "AND uploaded_by = :uid" if user_id else ""
    author_rows = (
        await db.execute(
            text(author_sql.format(user_filter=user_filter)),
            {"uid": user_id} if user_id else {},
        )
    ).all()
    top_authors = [{"author": r.author, "count": r.cnt} for r in author_rows]

    # ── Top queries (scoped to user's search history) ─────────────────────────
    history_query = (
        select(SearchHistory.query_text)
        .order_by(SearchHistory.created_at.desc())
        .limit(200)
    )
    if user_id:
        history_query = history_query.where(SearchHistory.user_id == user_id)
    history_rows = (await db.execute(history_query)).scalars().all()
    counter = Counter(history_rows)
    top_queries = [q for q, _ in counter.most_common(10)]

    return {
        "total_papers": total_papers,
        "total_chunks": total_chunks,
        "by_category": by_category,
        "top_authors": top_authors,
        "by_year": by_year,
        "top_queries": top_queries,
    }
