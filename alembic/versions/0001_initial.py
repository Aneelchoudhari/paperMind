"""Initial migration — all 5 tables + tsvector trigger.

Revision ID: 0001_initial
Revises: 
Create Date: 2026-07-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # papers
    op.create_table(
        "papers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("authors", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("publication_year", sa.Integer, nullable=True),
        sa.Column("abstract", sa.Text, nullable=True),
        sa.Column("keywords", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("doi", sa.String(255), nullable=True),
        sa.Column("journal_or_venue", sa.String(255), nullable=True),
        sa.Column("num_pages", sa.Integer, nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("file_hash", sa.String(64), unique=True, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="processing"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_papers_category", "papers", ["category"])
    op.create_index("idx_papers_status", "papers", ["status"])

    # chunks
    op.create_table(
        "chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("paper_id", sa.String(36), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("section_title", sa.String(255), nullable=True),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("tsv", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_chunks_paper_id", "chunks", ["paper_id"])
    # GIN index for full-text search
    op.execute("CREATE INDEX idx_chunks_tsv ON chunks USING GIN(to_tsvector('english', COALESCE(text, '')))")

    # Create tsvector trigger function and trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION chunks_tsv_update_fn() RETURNS trigger AS $$
        BEGIN
            NEW.tsv := to_tsvector('english', COALESCE(NEW.text, ''));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER chunks_tsv_update
        BEFORE INSERT OR UPDATE ON chunks
        FOR EACH ROW EXECUTE FUNCTION chunks_tsv_update_fn();
    """)

    # search_history
    op.create_table(
        "search_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("query_text", sa.Text, nullable=False),
        sa.Column("query_type", sa.String(20), nullable=False),
        sa.Column("retrieved_paper_ids", postgresql.ARRAY(sa.String(36)), nullable=True),
        sa.Column("answer_text", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_search_history_user", "search_history", ["user_id"])

    # qa_citations
    op.create_table(
        "qa_citations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("search_history_id", sa.String(36), sa.ForeignKey("search_history.id", ondelete="CASCADE"), nullable=False),
        sa.Column("paper_id", sa.String(36), sa.ForeignKey("papers.id"), nullable=False),
        sa.Column("chunk_id", sa.String(36), sa.ForeignKey("chunks.id"), nullable=False),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("section_title", sa.String(255), nullable=True),
        sa.Column("relevance_score", sa.Float, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("qa_citations")
    op.drop_table("search_history")
    op.execute("DROP TRIGGER IF EXISTS chunks_tsv_update ON chunks")
    op.execute("DROP FUNCTION IF EXISTS chunks_tsv_update_fn()")
    op.drop_table("chunks")
    op.drop_table("papers")
    op.drop_table("users")
