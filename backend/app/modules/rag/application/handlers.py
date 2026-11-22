"""Subscribe the RAG module to Knowledge Base events (idempotent)."""
from app.modules.knowledge_base.public import DocumentDeleted, DocumentUploaded
from app.modules.rag.application.indexing import on_document_deleted, on_document_uploaded
from app.platform.events import get_event_bus

_registered_buses: set[int] = set()


def register_handlers() -> None:
    bus = get_event_bus()
    if id(bus) in _registered_buses:
        return
    bus.subscribe(DocumentUploaded, on_document_uploaded)
    bus.subscribe(DocumentDeleted, on_document_deleted)
    _registered_buses.add(id(bus))
