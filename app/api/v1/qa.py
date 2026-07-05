"""QA router — grounded question answering."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.db.session import get_db
from app.models.models import User
from app.schemas.schemas import QARequest, QAResponse
from app.services.qa_service import answer_question

router = APIRouter()


@router.post("", response_model=QAResponse)
async def ask_question(
    body: QARequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ask a question and get a grounded answer with citations."""
    filters = body.filters.model_dump(exclude_none=True) if body.filters else None
    result = await answer_question(
        question=body.question,
        user_id=current_user.id,
        db=db,
        filters=filters,
    )
    return QAResponse(**result)
