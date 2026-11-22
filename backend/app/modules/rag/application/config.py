"""RAG configuration (environment-driven). The embedding model is independent of the chat LLM."""
import os

EMBEDDING_MODEL = os.environ.get("RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = 384  # schema is fixed to vector(384); changing models requires a migration + re-embedding


def chunk_size() -> int:
    return int(os.environ.get("RAG_CHUNK_SIZE", "700"))


def chunk_overlap() -> int:
    return int(os.environ.get("RAG_CHUNK_OVERLAP", "120"))
