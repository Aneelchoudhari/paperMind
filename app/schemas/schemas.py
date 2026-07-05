"""Pydantic request/response schemas."""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ── Auth ─────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    full_name: Optional[str]
    role: str
    created_at: datetime


# ── Papers ───────────────────────────────────────────────────────────────────

class PaperOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: Optional[str]
    authors: Optional[list[str]]
    publication_year: Optional[int]
    abstract: Optional[str]
    keywords: Optional[list[str]]
    doi: Optional[str]
    journal_or_venue: Optional[str]
    num_pages: Optional[int]
    category: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime


class PaperStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str
    error_message: Optional[str]


class PaperUpdateRequest(BaseModel):
    title: Optional[str] = None
    authors: Optional[list[str]] = None
    publication_year: Optional[int] = None
    abstract: Optional[str] = None
    keywords: Optional[list[str]] = None
    doi: Optional[str] = None
    journal_or_venue: Optional[str] = None
    category: Optional[str] = None


# ── Search ───────────────────────────────────────────────────────────────────

class SearchFilters(BaseModel):
    category: Optional[str] = None
    year_min: Optional[int] = None
    year_max: Optional[int] = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    mode: str = Field(default="hybrid", pattern="^(keyword|semantic|hybrid)$")
    filters: Optional[SearchFilters] = None
    top_k: int = Field(default=10, ge=1, le=50)


class SearchResultItem(BaseModel):
    chunk_id: str
    paper_id: str
    paper_title: Optional[str]
    page_number: Optional[int]
    section_title: Optional[str]
    text_snippet: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    total_results: int


# ── QA ───────────────────────────────────────────────────────────────────────

class QARequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    filters: Optional[SearchFilters] = None


class CitationOut(BaseModel):
    marker: int
    chunk_id: str
    paper_id: Optional[str]
    paper_title: Optional[str]
    page_number: Optional[int]
    section_title: Optional[str]


class QAResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    sufficient_evidence: bool
    search_history_id: str


# ── Analytics ────────────────────────────────────────────────────────────────

class CategoryCount(BaseModel):
    category: Optional[str]
    count: int


class AuthorCount(BaseModel):
    author: str
    count: int


class YearCount(BaseModel):
    year: Optional[int]
    count: int


class AnalyticsOverview(BaseModel):
    total_papers: int
    total_chunks: int
    by_category: list[CategoryCount]
    top_authors: list[AuthorCount]
    by_year: list[YearCount]
    top_queries: list[str]


# ── Search History ────────────────────────────────────────────────────────────

class HistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    query_text: str
    query_type: str
    answer_text: Optional[str]
    created_at: datetime


# ── Error envelope ────────────────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
