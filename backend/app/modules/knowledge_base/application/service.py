"""Knowledge Base use cases: upload/ingest, list, delete, status updates, sample loading.

Indexing is NOT done here. After metadata is stored this module publishes a `DocumentUploaded`
event; the RAG module (which depends on this module's public interface) subscribes and builds
chunks/embeddings, then reports back via `mark_indexed` / `mark_failed`.
"""
import hashlib
import logging
import re
from pathlib import Path
from uuid import UUID

from app.modules.knowledge_base.application import config
from app.modules.knowledge_base.domain.cleaning import clean_pages
from app.modules.knowledge_base.domain.models import (
    STATUS_FAILED,
    STATUS_INDEXED,
    DocumentDeleted,
    DocumentInfo,
    DocumentUploaded,
)
from app.modules.knowledge_base.domain.validation import (
    DuplicateDocument,
    NotFoundError,
    UnreadableDocument,
    validate_pdf_upload,
)
from app.modules.knowledge_base.infrastructure.pdf_extractor import extract_pdf
from app.modules.knowledge_base.infrastructure.repository import DocumentRepository
from app.platform.audit_events import AuditEvent
from app.platform.db import unit_of_work
from app.platform.events import get_event_bus

log = logging.getLogger("app.knowledge_base")


def _display_name(explicit: str | None, title: str | None, filename: str) -> str:
    if explicit and explicit.strip():
        return explicit.strip()[:200]
    if title and title.strip():
        return title.strip()[:200]
    stem = re.sub(r"^\d+[_-]", "", Path(filename).stem)
    return stem.replace("_", " ").replace("-", " ").strip().title()[:200] or filename


def _audit(actor: str, action: str, doc_id: UUID, **detail) -> None:
    get_event_bus().publish(AuditEvent(actor=actor, action=action, resource=f"knowledge_document:{doc_id}", detail=detail))


def upload_document(
    filename: str | None, data: bytes, *, display_name: str | None = None, is_sample: bool = False,
    actor: str = "system",
) -> DocumentInfo:
    validate_pdf_upload(filename, data, config.max_upload_bytes())
    assert filename is not None
    extracted = extract_pdf(data, config.max_pages())
    pages = clean_pages(extracted.raw_pages)
    if not pages:
        raise UnreadableDocument("No extractable text found (scanned/image-only PDFs are not supported).")

    sha = hashlib.sha256(data).hexdigest()
    with unit_of_work() as session:
        repo = DocumentRepository(session)
        existing = repo.find_by_sha256(sha)
        if existing:
            raise DuplicateDocument(f"This file was already uploaded as '{existing.name}'.")
        doc = repo.insert(
            name=_display_name(display_name, extracted.title, filename),
            original_filename=Path(filename).name[:255],
            sha256=sha,
            size_bytes=len(data),
            page_count=extracted.page_count,
            is_sample=is_sample,
        )

    # Metadata is committed; indexing happens in subscribers (each in its own transaction).
    _audit(actor, "knowledge.document.upload", doc.id, name=doc.name, pages=doc.page_count, sample=is_sample)
    get_event_bus().publish(DocumentUploaded(document_id=doc.id, name=doc.name, pages=tuple(pages)))
    return get_document(doc.id)


def get_document(document_id: UUID) -> DocumentInfo:
    with unit_of_work() as session:
        doc = DocumentRepository(session).get(document_id)
    if doc is None:
        raise NotFoundError("Document not found.")
    return doc


def list_documents(limit: int = 50, offset: int = 0) -> tuple[list[DocumentInfo], int]:
    with unit_of_work() as session:
        repo = DocumentRepository(session)
        return repo.list(limit, offset), repo.count()


def delete_document(document_id: UUID, actor: str = "system") -> None:
    with unit_of_work() as session:
        if not DocumentRepository(session).delete(document_id):
            raise NotFoundError("Document not found.")
    _audit(actor, "knowledge.document.delete", document_id)
    get_event_bus().publish(DocumentDeleted(document_id=document_id))


def mark_indexed(document_id: UUID, chunk_count: int) -> None:
    with unit_of_work() as session:
        DocumentRepository(session).set_status(document_id, STATUS_INDEXED, chunk_count, None)


def mark_failed(document_id: UUID, message: str) -> None:
    with unit_of_work() as session:
        DocumentRepository(session).set_status(document_id, STATUS_FAILED, 0, message[:500])


def load_sample_documents(directory: str | None = None, actor: str = "system") -> dict[str, list[str]]:
    """Ingest the fictional demo PDFs found in a directory; already-loaded files are skipped."""
    folder = Path(directory or config.sample_docs_dir())
    if not folder.is_dir():
        raise NotFoundError("Sample documents directory is not available on the server.")
    loaded: list[str] = []
    skipped: list[str] = []
    for pdf in sorted(folder.glob("*.pdf")):
        try:
            upload_document(pdf.name, pdf.read_bytes(), is_sample=True, actor=actor)
            loaded.append(pdf.name)
        except DuplicateDocument:
            skipped.append(pdf.name)
    return {"loaded": loaded, "skipped": skipped}
