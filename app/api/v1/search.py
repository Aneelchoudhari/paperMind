"""Search router — keyword / semantic / hybrid search."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.db.session import get_db
from app.models.models import SearchHistory, User
from app.schemas.schemas import SearchRequest, SearchResponse, SearchResultItem
from app.services.reranker_service import rerank
from app.services.retrieval_service import hybrid_search

router = APIRouter()


@router.post("", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    filters = body.filters.model_dump(exclude_none=True) if body.filters else None

    ranked_ids, chunk_map = await hybrid_search(
        body.query,
        db,
        mode=body.mode,
        top_k=50,
        filters=filters,
        user_id=current_user.id,
    )

    # For search (not QA) we skip the cross-encoder to keep it fast
    # but we apply top_k limit
    final_ids = ranked_ids[: body.top_k]

    results = []
    for i, cid in enumerate(final_ids):
        detail = chunk_map.get(cid, {})
        results.append(
            SearchResultItem(
                chunk_id=cid,
                paper_id=detail.get("paper_id", ""),
                paper_title=detail.get("paper_title"),
                page_number=detail.get("page_number"),
                section_title=detail.get("section_title"),
                text_snippet=detail.get("text", "")[:400],
                score=detail.get("score", 0.0),
            )
        )

    # Persist to search history
    paper_ids = list({r.paper_id for r in results if r.paper_id})
    db.add(
        SearchHistory(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            query_text=body.query,
            query_type=body.mode,
            retrieved_paper_ids=paper_ids,
        )
    )
    await db.commit()

    return SearchResponse(results=results, total_results=len(results))
