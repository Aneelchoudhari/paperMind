"""Papers router — upload, list, detail, status, delete, patch, related."""
import hashlib
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.db.vector_store import delete_chunks_by_paper
from app.models.models import Chunk, Paper, User
from app.providers.storage_provider import delete_paper as storage_delete, save_paper
from app.schemas.schemas import PaperOut, PaperStatusOut, PaperUpdateRequest
from app.workers.tasks import process_paper

logger = get_logger(__name__)
router = APIRouter()

_MAX_BYTES = settings.max_upload_size_mb * 1024 * 1024
_PDF_MAGIC = b"%PDF-"


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=dict)
async def upload_paper(
    file: UploadFile = File(...),
    category: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF. Returns 202 immediately; ingestion runs in background."""
    # Validate MIME + size
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(400, {"code": "INVALID_FILE_TYPE", "message": "Only PDF files are accepted"})

    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(413, {"code": "FILE_TOO_LARGE", "message": f"Max upload size is {settings.max_upload_size_mb}MB"})
    if not data.startswith(_PDF_MAGIC):
        raise HTTPException(400, {"code": "INVALID_PDF", "message": "File is not a valid PDF"})

    # SHA-256 dedup
    file_hash = hashlib.sha256(data).hexdigest()
    existing = (await db.execute(select(Paper).where(Paper.file_hash == file_hash))).scalar_one_or_none()
    if existing:
        raise HTTPException(409, {"code": "DUPLICATE_PAPER", "message": f"Paper already exists", "paper_id": existing.id})

    paper_id = str(uuid.uuid4())
    file_path = save_paper(paper_id, data)

    paper = Paper(
        id=paper_id,
        uploaded_by=current_user.id,
        file_path=file_path,
        file_hash=file_hash,
        category=category,
        status="processing",
    )
    db.add(paper)
    await db.commit()

    # Enqueue background ingestion
    process_paper.delay(paper_id)
    logger.info("Uploaded paper %s, ingestion enqueued", paper_id)
    return {"paper_id": paper_id, "status": "processing"}


@router.get("", response_model=list[PaperOut])
async def list_papers(
    category: Optional[str] = Query(None),
    year_min: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    q: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Paper).where(Paper.uploaded_by == current_user.id)
    if category:
        stmt = stmt.where(Paper.category == category)
    if year_min:
        stmt = stmt.where(Paper.publication_year >= year_min)
    if status_filter:
        stmt = stmt.where(Paper.status == status_filter)
    if q:
        stmt = stmt.where(Paper.title.ilike(f"%{q}%"))
    stmt = stmt.order_by(Paper.created_at.desc()).limit(limit).offset(offset)
    papers = (await db.execute(stmt)).scalars().all()
    return papers


@router.get("/{paper_id}", response_model=PaperOut)
async def get_paper(
    paper_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    paper = await _get_paper_or_404(paper_id, db)
    return paper


@router.get("/{paper_id}/status", response_model=PaperStatusOut)
async def get_paper_status(
    paper_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    paper = await _get_paper_or_404(paper_id, db)
    return paper


@router.patch("/{paper_id}", response_model=PaperOut)
async def update_paper(
    paper_id: str,
    body: PaperUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    paper = await _get_paper_or_404(paper_id, db)
    _check_owner(paper, current_user)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(paper, field, value)
    await db.commit()
    await db.refresh(paper)
    return paper


@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_paper(
    paper_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    paper = await _get_paper_or_404(paper_id, db)
    _check_owner(paper, current_user)

    # Delete vectors
    try:
        delete_chunks_by_paper(paper_id)
    except Exception as e:
        logger.warning("ChromaDB delete failed for paper %s: %s", paper_id, e)

    # Delete file
    try:
        storage_delete(paper.file_path)
    except Exception as e:
        logger.warning("Storage delete failed: %s", e)

    await db.delete(paper)
    await db.commit()


@router.get("/{paper_id}/related", response_model=list[PaperOut])
async def get_related_papers(
    paper_id: str,
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return papers by same authors or similar topic."""
    paper = await _get_paper_or_404(paper_id, db)

    # Same author
    same_author: list[Paper] = []
    if paper.authors:
        stmt = (
            select(Paper)
            .where(Paper.id != paper_id)
            .where(Paper.status == "ready")
            .where(Paper.authors.overlap(paper.authors))  # type: ignore[attr-defined]
            .limit(limit)
        )
        same_author = (await db.execute(stmt)).scalars().all()

    if len(same_author) >= limit:
        return same_author[:limit]

    # Fallback: same category
    if paper.category and len(same_author) < limit:
        stmt = (
            select(Paper)
            .where(Paper.id != paper_id)
            .where(Paper.status == "ready")
            .where(Paper.category == paper.category)
            .limit(limit - len(same_author))
        )
        same_cat = (await db.execute(stmt)).scalars().all()
        combined = {p.id: p for p in same_author}
        for p in same_cat:
            combined.setdefault(p.id, p)
        return list(combined.values())[:limit]

    return same_author


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _get_paper_or_404(paper_id: str, db: AsyncSession) -> Paper:
    paper = (await db.execute(select(Paper).where(Paper.id == paper_id))).scalar_one_or_none()
    if not paper:
        raise HTTPException(404, {"code": "PAPER_NOT_FOUND", "message": f"Paper {paper_id} not found"})
    return paper


def _check_owner(paper: Paper, user: User) -> None:
    if user.role != "admin" and paper.uploaded_by != user.id:
        raise HTTPException(403, {"code": "FORBIDDEN", "message": "You don't have permission to modify this paper"})
