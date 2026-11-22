"""Similarity search over stored chunks."""
from dataclasses import dataclass
from uuid import UUID

from app.modules.rag.application import config
from app.modules.rag.domain.injection import ContextItem, build_untrusted_context
from app.modules.rag.infrastructure.chunk_repository import ChunkRepository
from app.modules.rag.infrastructure.embedder import get_default_embedder
from app.platform.db import unit_of_work
from app.platform.errors import AppError

MAX_QUERY_CHARS = 2000
MAX_K = 20


class InvalidSearchRequest(AppError):
    status_code = 422
    code = "invalid_search_request"


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: UUID
    document_id: UUID
    document_name: str
    page_number: int
    chunk_index: int
    excerpt: str
    score: float  # cosine similarity, 1.0 = identical direction
    injection_flagged: bool
    injection_signals: tuple[str, ...]


def search(query: str, k: int = 5, *, embedder=None) -> list[RetrievedChunk]:
    query = (query or "").strip()
    if not query:
        raise InvalidSearchRequest("Query must not be empty.")
    if len(query) > MAX_QUERY_CHARS:
        raise InvalidSearchRequest(f"Query exceeds {MAX_QUERY_CHARS} characters.")
    if not 1 <= k <= MAX_K:
        raise InvalidSearchRequest(f"k must be between 1 and {MAX_K}.")
    vector = (embedder or get_default_embedder()).embed([query])[0]
    with unit_of_work() as session:
        hits = ChunkRepository(session).search(vector, k)
    return [
        RetrievedChunk(h.chunk_id, h.document_id, h.document_name, h.page_number, h.chunk_index,
                       h.content, round(h.score, 4), h.injection_flagged, tuple(h.injection_signals))
        for h in hits
    ]


def format_context(chunks: list[RetrievedChunk]) -> str:
    """LLM-ready context: delimited, labelled as untrusted data, flagged chunks withheld."""
    return build_untrusted_context(
        [ContextItem(c.document_name, c.page_number, c.excerpt, c.injection_flagged) for c in chunks]
    )


def embedding_info() -> dict[str, str | int]:
    return {"model": config.EMBEDDING_MODEL, "dimensions": config.EMBEDDING_DIM}
