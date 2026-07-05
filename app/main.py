"""PaperMind AI — FastAPI application factory."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, papers, search, qa, analytics, users
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    application = FastAPI(
        title="PaperMind AI",
        description=(
            "RAG system for AI/ML research papers. Upload PDFs, search them "
            "semantically, and ask grounded questions with exact citations."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ──────────────────────────────────────────────────
    application.include_router(auth.router, prefix="/auth", tags=["auth"])
    application.include_router(papers.router, prefix="/papers", tags=["papers"])
    application.include_router(search.router, prefix="/search", tags=["search"])
    application.include_router(qa.router, prefix="/qa", tags=["qa"])
    application.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
    application.include_router(users.router, prefix="/users", tags=["users"])

    @application.get("/health", tags=["health"])
    async def health_check():
        return {"status": "ok", "service": "PaperMind AI"}

    logger.info("PaperMind AI application created")
    return application


app = create_app()
