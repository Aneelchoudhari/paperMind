"""Analytics router."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.db.session import get_db
from app.models.models import User
from app.schemas.schemas import AnalyticsOverview
from app.services.analytics_service import get_analytics_overview

router = APIRouter()


@router.get("/overview", response_model=AnalyticsOverview)
async def analytics_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return aggregated analytics scoped to the current user."""
    data = await get_analytics_overview(db, user_id=current_user.id)
    return AnalyticsOverview(**data)
