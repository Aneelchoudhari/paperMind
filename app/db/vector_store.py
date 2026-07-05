"""ChromaDB persistent client wrapper.

Collection: paper_chunks
  id         → chunk UUID (matches chunks.id in Postgres)
  embedding  → float[dim] from embedding model
  document   → raw chunk text
  metadata   → {paper_id, paper_title, page_number, section_title,
                chunk_index, category}
"""
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client = None
_collection = None


def get_chroma_client():
    global _client
    if _client is None:
        _client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        logger.info(
            "ChromaDB client connected to %s:%s",
            settings.chroma_host,
            settings.chroma_port,
        )
    return _client


def get_collection():
    """Get or create the paper_chunks collection."""
    global _collection
    if _collection is None:
        client = get_chroma_client()
        _collection = client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "ChromaDB collection '%s' ready (%d items)",
            settings.chroma_collection,
            _collection.count(),
        )
    return _collection


def upsert_chunks(
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    """Bulk-upsert chunks into ChromaDB."""
    collection = get_collection()
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )
    logger.info("Upserted %d chunks into ChromaDB", len(ids))


def query_similar(
    query_embedding: list[float],
    n_results: int = 50,
    where: dict | None = None,
) -> dict:
    """Query the collection by vector similarity."""
    collection = get_collection()
    kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where
    return collection.query(**kwargs)


def delete_chunks_by_paper(paper_id: str) -> None:
    """Delete all chunks belonging to a paper."""
    collection = get_collection()
    collection.delete(where={"paper_id": paper_id})
    logger.info("Deleted ChromaDB chunks for paper %s", paper_id)
