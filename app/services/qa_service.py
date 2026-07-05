"""QA service — grounded RAG question answering with citation enforcement.

Spec §6:
  §6.1 Flow: hybrid retrieval → rerank → build prompt → LLM → validate → persist
  §6.2 Exact prompt template (verbatim)
  §6.3 Citation enforcement (3 validation rules)
  §6.4 API contract
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Optional

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.models import QACitation, SearchHistory
from app.providers.llm_provider import get_llm_provider
from app.services.reranker_service import rerank
from app.services.retrieval_service import hybrid_search

logger = get_logger(__name__)

FALLBACK_ANSWER = "I could not find sufficient evidence in the uploaded papers."

_SYSTEM_PROMPT = """\
You are PaperMind AI, a research assistant that answers questions strictly
using the provided paper excerpts. Follow these rules exactly:

1. Use ONLY the information in the provided excerpts. Do not use outside
   knowledge, even if you know the answer.
2. Every factual sentence in your answer must be followed by a citation
   marker like [1], [2] referencing the excerpt number(s) that support it.
3. If the excerpts do not contain enough information to answer the
   question, respond with exactly: "I could not find sufficient evidence
   in the uploaded papers." Do not attempt a partial guess.
4. Do not fabricate paper names, authors, numbers, or results that are
   not explicitly present in the excerpts.
5. Return your response as JSON with this exact schema:
   {
     "answer": "string, with inline [n] citation markers",
     "citations": [
       {"marker": 1, "chunk_id": "string", "paper_title": "string",
        "page_number": int, "section_title": "string"}
     ],
     "sufficient_evidence": true | false
   }\
"""


async def answer_question(
    question: str,
    user_id: str,
    db: AsyncSession,
    filters: Optional[dict] = None,
) -> dict:
    """Full RAG QA pipeline.

    Returns a dict with keys: answer, citations, sufficient_evidence,
    search_history_id.
    """
    # ── Retrieval ─────────────────────────────────────────────────────────────
    ranked_ids, chunk_map = await hybrid_search(
        question, db, mode="hybrid", filters=filters, user_id=user_id
    )

    # ── Rerank → top 5 ───────────────────────────────────────────────────────
    top_chunks = rerank(question, ranked_ids, chunk_map)

    # ── Build prompt ──────────────────────────────────────────────────────────
    if not top_chunks:
        return await _fallback_response(question, user_id, db, chunk_ids=[])

    excerpts_text = _build_excerpts(top_chunks)
    user_msg = f"EXCERPTS:\n{excerpts_text}\n\nUSER QUESTION:\n{question}"

    valid_chunk_ids = {c["id"] for c in top_chunks}

    # ── LLM call with retry ───────────────────────────────────────────────────
    llm = get_llm_provider()
    raw_json = None
    for attempt in range(2):
        try:
            if attempt == 0:
                raw = llm.complete(_SYSTEM_PROMPT, user_msg, json_mode=True)
            else:
                raw = llm.complete(
                    _SYSTEM_PROMPT,
                    user_msg + "\n\nYour last response was not valid JSON. Return ONLY valid JSON.",
                    json_mode=True,
                )
            raw_stripped = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
            raw_json = json.loads(raw_stripped)
            break
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("LLM attempt %d failed: %s", attempt + 1, e)

    if raw_json is None:
        return await _fallback_response(question, user_id, db, chunk_ids=list(valid_chunk_ids))

    # ── Citation enforcement (spec §6.3) ──────────────────────────────────────
    validated = _validate_citations(raw_json, valid_chunk_ids, top_chunks)

    # ── Persist to search_history + qa_citations ─────────────────────────────
    history_id = str(uuid.uuid4())
    history_row = SearchHistory(
        id=history_id,
        user_id=user_id,
        query_text=question,
        query_type="qa",
        retrieved_paper_ids=list({c["paper_id"] for c in top_chunks}),
        answer_text=validated["answer"],
    )
    db.add(history_row)
    await db.flush()

    for cit in validated.get("citations", []):
        # Find the chunk in top_chunks to get paper_id
        chunk_detail = next(
            (c for c in top_chunks if c["id"] == cit.get("chunk_id")), None
        )
        if chunk_detail:
            db.add(
                QACitation(
                    search_history_id=history_id,
                    paper_id=chunk_detail["paper_id"],
                    chunk_id=cit["chunk_id"],
                    page_number=cit.get("page_number"),
                    section_title=cit.get("section_title"),
                    relevance_score=chunk_detail.get("rerank_score"),
                )
            )
    await db.commit()

    return {
        "answer": validated["answer"],
        "citations": [
            {
                "marker": c.get("marker"),
                "chunk_id": c.get("chunk_id"),
                "paper_id": next(
                    (ch["paper_id"] for ch in top_chunks if ch["id"] == c.get("chunk_id")),
                    None,
                ),
                "paper_title": c.get("paper_title"),
                "page_number": c.get("page_number"),
                "section_title": c.get("section_title"),
            }
            for c in validated.get("citations", [])
        ],
        "sufficient_evidence": validated["sufficient_evidence"],
        "search_history_id": history_id,
    }


# ── Private helpers ──────────────────────────────────────────────────────────


def _build_excerpts(chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        title = chunk.get("paper_title") or "Unknown"
        page = chunk.get("page_number") or "?"
        section = chunk.get("section_title") or "Unknown"
        text = chunk.get("text", "")
        parts.append(
            f'[{i}] (Chunk ID: "{chunk.get("id")}", Paper: "{title}", Page {page}, Section "{section}")\n{text}'
        )
    return "\n\n".join(parts)


def _validate_citations(
    raw: dict,
    valid_chunk_ids: set[str],
    top_chunks: list[dict],
) -> dict:
    """Apply the three citation enforcement rules from spec §6.3."""
    answer = raw.get("answer", "")
    citations = raw.get("citations", [])
    sufficient = raw.get("sufficient_evidence", False)

    # Rule 4: if sufficient_evidence is false, force fallback
    if not sufficient:
        return {"answer": FALLBACK_ANSWER, "citations": [], "sufficient_evidence": False}

    # Rule 3: reject if any citation chunk_id was not in the retrieved set
    for cit in citations:
        if cit.get("chunk_id") not in valid_chunk_ids:
            logger.warning(
                "Hallucinated chunk_id %s — forcing fallback", cit.get("chunk_id")
            )
            return {"answer": FALLBACK_ANSWER, "citations": [], "sufficient_evidence": False}

    # Rule 2: every inline marker [n] must exist in citations
    markers_in_text = set(int(m) for m in re.findall(r"\[(\d+)\]", answer))
    marker_nums = {c.get("marker") for c in citations}
    dangling = markers_in_text - marker_nums
    if dangling:
        logger.warning("Dangling citation markers: %s", dangling)
        # Remove dangling markers from answer text
        for m in dangling:
            answer = answer.replace(f"[{m}]", "")

    return {"answer": answer, "citations": citations, "sufficient_evidence": True}


async def _fallback_response(
    question: str,
    user_id: str,
    db: AsyncSession,
    chunk_ids: list[str],
) -> dict:
    history_id = str(uuid.uuid4())
    db.add(
        SearchHistory(
            id=history_id,
            user_id=user_id,
            query_text=question,
            query_type="qa",
            retrieved_paper_ids=[],
            answer_text=FALLBACK_ANSWER,
        )
    )
    await db.commit()
    return {
        "answer": FALLBACK_ANSWER,
        "citations": [],
        "sufficient_evidence": False,
        "search_history_id": history_id,
    }
