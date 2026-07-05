"""Cross-encoder re-ranking service.

Spec §5.4:
  Model: cross-encoder/ms-marco-MiniLM-L-6-v2
  Input: top-20 RRF chunks + original query
  Output: sorted by relevance score → top-5
"""
from __future__ import annotations

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import torch
torch.set_num_threads(1)
from sentence_transformers import CrossEncoder

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_reranker: CrossEncoder | None = None


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        logger.info("Loading cross-encoder reranker: %s", _RERANKER_MODEL)
        _reranker = CrossEncoder(_RERANKER_MODEL)
        logger.info("Reranker loaded")
    return _reranker


def rerank(
    query: str,
    chunk_ids: list[str],
    chunk_map: dict[str, dict],
    top_n: int | None = None,
) -> list[dict]:
    """Re-rank chunks by cross-encoder relevance score.

    Args:
        query: The search query.
        chunk_ids: Ordered list of chunk IDs from RRF.
        chunk_map: Map from chunk_id → chunk detail dict (must have 'text').
        top_n: Number of top chunks to return. Defaults to settings.rerank_top_n.

    Returns:
        List of chunk dicts sorted by descending relevance score,
        each augmented with 'rerank_score'.
    """
    if top_n is None:
        top_n = settings.rerank_top_n

    # Only rerank chunks we have details for
    valid_ids = [cid for cid in chunk_ids if cid in chunk_map]
    if not valid_ids:
        return []

    reranker = _get_reranker()
    pairs = [(query, chunk_map[cid]["text"]) for cid in valid_ids]
    scores = reranker.predict(pairs)

    scored = sorted(
        zip(valid_ids, scores),
        key=lambda x: x[1],
        reverse=True,
    )[:top_n]

    results = []
    for cid, score in scored:
        item = dict(chunk_map[cid])
        item["rerank_score"] = float(score)
        results.append(item)

    logger.info(
        "Reranked %d → %d chunks (top score=%.3f)",
        len(valid_ids), len(results),
        results[0]["rerank_score"] if results else 0,
    )
    return results
