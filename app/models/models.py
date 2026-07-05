"""SQLAlchemy ORM models."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Float,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── User ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    papers: Mapped[list["Paper"]] = relationship(back_populates="uploader")
    search_history: Mapped[list["SearchHistory"]] = relationship(back_populates="user")


# ── Paper ────────────────────────────────────────────────────────────────────

class Paper(Base):
    __tablename__ = "papers"
    __table_args__ = (
        Index("idx_papers_category", "category"),
        Index("idx_papers_status", "status"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    uploaded_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id")
    )
    title: Mapped[str | None] = mapped_column(String(500))
    authors: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    publication_year: Mapped[int | None] = mapped_column(Integer)
    abstract: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    doi: Mapped[str | None] = mapped_column(String(255))
    journal_or_venue: Mapped[str | None] = mapped_column(String(255))
    num_pages: Mapped[int | None] = mapped_column(Integer)
    category: Mapped[str | None] = mapped_column(String(100))
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="processing"
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    uploader: Mapped["User"] = relationship(back_populates="papers")
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )


# ── Chunk ────────────────────────────────────────────────────────────────────

class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        Index("idx_chunks_paper_id", "paper_id"),
        Index("idx_chunks_tsv", "tsv", postgresql_using="gin"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    paper_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section_title: Mapped[str | None] = mapped_column(String(255))
    page_number: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    # tsv is managed by a Postgres trigger — we declare it as a server-default column
    tsv: Mapped[str | None] = mapped_column(
        Text, nullable=True, server_default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    paper: Mapped["Paper"] = relationship(back_populates="chunks")


# ── Search History ───────────────────────────────────────────────────────────

class SearchHistory(Base):
    __tablename__ = "search_history"
    __table_args__ = (Index("idx_search_history_user", "user_id"),)

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id")
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    query_type: Mapped[str] = mapped_column(String(20), nullable=False)
    retrieved_paper_ids: Mapped[list[str] | None] = mapped_column(ARRAY(String(36)))
    answer_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="search_history")
    citations: Mapped[list["QACitation"]] = relationship(
        back_populates="search_history_entry", cascade="all, delete-orphan"
    )


# ── QA Citation ──────────────────────────────────────────────────────────────

class QACitation(Base):
    __tablename__ = "qa_citations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    search_history_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("search_history.id", ondelete="CASCADE"),
        nullable=False,
    )
    paper_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("papers.id"), nullable=False
    )
    chunk_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chunks.id"), nullable=False
    )
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(String(255))
    relevance_score: Mapped[float | None] = mapped_column(Float)

    search_history_entry: Mapped["SearchHistory"] = relationship(back_populates="citations")
