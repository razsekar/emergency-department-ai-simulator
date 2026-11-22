"""Public interface of the Knowledge Base module. Other modules may import ONLY this file.

Owns document metadata and the ingestion workflow (validate -> extract -> clean -> store ->
publish `DocumentUploaded`). Indexing is performed by event subscribers (the RAG module).
"""
from uuid import UUID

from app.modules.knowledge_base.application import service as _service
from app.modules.knowledge_base.domain.models import (  # noqa: F401  (public contract types)
    STATUS_FAILED,
    STATUS_INDEXED,
    STATUS_PROCESSING,
    DocumentDeleted,
    DocumentInfo,
    DocumentUploaded,
    PageText,
)


def upload_document(
    filename: str | None, data: bytes, *, display_name: str | None = None, is_sample: bool = False,
    actor: str = "system",
) -> DocumentInfo:
    """Validate, extract, store metadata, and trigger indexing (event). Raises AppError subclasses."""
    return _service.upload_document(filename, data, display_name=display_name, is_sample=is_sample, actor=actor)


def list_documents(limit: int = 50, offset: int = 0) -> tuple[list[DocumentInfo], int]:
    return _service.list_documents(limit, offset)


def get_document(document_id: UUID) -> DocumentInfo:
    return _service.get_document(document_id)


def delete_document(document_id: UUID, actor: str = "system") -> None:
    _service.delete_document(document_id, actor)


def mark_document_indexed(document_id: UUID, chunk_count: int) -> None:
    _service.mark_indexed(document_id, chunk_count)


def mark_document_failed(document_id: UUID, message: str) -> None:
    _service.mark_failed(document_id, message)


def load_sample_documents(directory: str | None = None, actor: str = "system") -> dict[str, list[str]]:
    return _service.load_sample_documents(directory, actor)
