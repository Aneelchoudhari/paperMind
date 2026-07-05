"""Users router — search history."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.db.session import get_db
from app.models.models import SearchHistory, User
from app.schemas.schemas import HistoryItem

router = APIRouter()


@router.get("/me/history", response_model=list[HistoryItem])
async def get_my_history(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return current user's query history, newest first."""
    rows = (
        await db.execute(
            select(SearchHistory)
            .where(SearchHistory.user_id == current_user.id)
            .order_by(SearchHistory.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return rows
