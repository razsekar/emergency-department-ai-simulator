"""Indexing use case: chunk -> injection scan -> embed -> store."""
import logging
from uuid import UUID

from app.modules.knowledge_base.public import (
    DocumentDeleted,
    DocumentUploaded,
    PageText,
    mark_document_failed,
    mark_document_indexed,
)
from app.modules.rag.application import config
from app.modules.rag.domain.chunking import chunk_pages
from app.modules.rag.domain.injection import scan_text
from app.modules.rag.infrastructure.chunk_repository import ChunkRepository, NewChunk
from app.modules.rag.infrastructure.embedder import get_default_embedder
from app.platform.db import unit_of_work

log = logging.getLogger("app.rag")


def index_document(
    document_id: UUID, name: str, pages: list[PageText], *, embedder=None,
    chunk_size: int | None = None, overlap: int | None = None,
) -> int:
    """Replace the stored chunks of a document with freshly built ones. Returns the chunk count."""
    embedder = embedder or get_default_embedder()
    chunks = chunk_pages(
        [(p.page_number, p.text) for p in pages],
        chunk_size or config.chunk_size(),
        config.chunk_overlap() if overlap is None else overlap,
    )
    if not chunks:
        raise ValueError("document produced no chunks")
    # Contextual header: the document title is embedded with each chunk (stored excerpt stays clean).
    # Measured on the sample policies, this ranks the right policy first far more often.
    vectors = embedder.embed([f"{name}\n{c.text}" for c in chunks])
    new_chunks = []
    for c, v in zip(chunks, vectors, strict=True):
        scan = scan_text(c.text)
        new_chunks.append(NewChunk(c.page_number, c.chunk_index, c.text, v, scan.flagged, scan.signals))
    with unit_of_work() as session:
        count = ChunkRepository(session).replace_document_chunks(document_id, name, new_chunks)
    flagged = sum(1 for c in new_chunks if c.injection_flagged)
    if flagged:
        log.warning("document %s: %d chunk(s) flagged for possible prompt injection", document_id, flagged)
    return count


def on_document_uploaded(event: DocumentUploaded) -> None:
    """Event handler: never raises (a failed index must not break the upload request)."""
    try:
        count = index_document(event.document_id, event.name, list(event.pages))
        mark_document_indexed(event.document_id, count)
    except Exception as exc:
        log.exception("indexing failed for %s", event.document_id)
        mark_document_failed(event.document_id, f"Indexing failed: {type(exc).__name__}")


def on_document_deleted(event: DocumentDeleted) -> None:
    with unit_of_work() as session:
        ChunkRepository(session).delete_document_chunks(event.document_id)
