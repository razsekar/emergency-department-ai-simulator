"""Public interface of the RAG module. Other modules may import ONLY this file.

Owns chunks, embeddings and vector search. Retrieved text is untrusted data: use `format_context`
to obtain a delimited, labelled block that is safe to place in an LLM prompt.
"""
from app.modules.rag.application import search as _search
from app.modules.rag.application.handlers import register_handlers
from app.modules.rag.application.search import RetrievedChunk  # noqa: F401  (public contract type)


def search(query: str, k: int = 5) -> list[RetrievedChunk]:
    """Top-k most similar chunks (document name, page, excerpt, cosine score, injection flags)."""
    return _search.search(query, k)


def format_context(chunks: list[RetrievedChunk]) -> str:
    """Render chunks as an UNTRUSTED-DATA context block for LLM prompts."""
    return _search.format_context(chunks)


def embedding_info() -> dict[str, str | int]:
    """Embedding model name and dimensionality (independent of the chat model)."""
    return _search.embedding_info()


__all__ = ["RetrievedChunk", "search", "format_context", "embedding_info", "register_handlers"]
