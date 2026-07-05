"""Pydantic Settings — all configuration read from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM ─────────────────────────────────────────────────────
    llm_provider: str = Field(default="openai", description="'openai' or 'gemini' or 'nvidia' or 'groq'")
    openai_api_key: str = Field(default="")
    gemini_api_key: str = Field(default="")
    nvidia_api_key: str = Field(default="")
    nvidia_model: str = Field(default="meta/llama-3.1-405b-instruct")
    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="llama-3.3-70b-specdec")
    llm_model: str = Field(default="gpt-4o-mini")  # swapped to mini for cost


    # ── Database ─────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://papermind:papermind_secret@localhost:5432/papermind"
    )

    # ── Redis ────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0")

    # ── ChromaDB ─────────────────────────────────────────────────
    chroma_host: str = Field(default="localhost")
    chroma_port: int = Field(default=8001)
    chroma_collection: str = Field(default="paper_chunks")

    # ── Storage ──────────────────────────────────────────────────
    storage_path: str = Field(default="./storage")
    max_upload_size_mb: int = Field(default=50)

    # ── Auth ─────────────────────────────────────────────────────
    secret_key: str = Field(default="change-me-in-production-min-32-chars!!")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=15)
    refresh_token_expire_days: int = Field(default=7)

    # ── Embeddings ───────────────────────────────────────────────
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2"
    )
    embedding_dim: int = Field(default=384)

    # ── Retrieval ────────────────────────────────────────────────
    bm25_top_k: int = Field(default=50)
    vector_top_k: int = Field(default=50)
    rrf_k: int = Field(default=60)
    rrf_top_n: int = Field(default=20)
    rerank_top_n: int = Field(default=5)

    # ── Rate limiting ────────────────────────────────────────────
    qa_rate_limit_per_hour: int = Field(default=30)

    # ── Analytics cache ──────────────────────────────────────────
    analytics_cache_ttl: int = Field(default=300)  # 5 minutes


settings = Settings()
