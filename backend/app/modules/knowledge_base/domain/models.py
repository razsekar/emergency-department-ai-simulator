"""Knowledge Base domain types."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

STATUS_PROCESSING = "processing"
STATUS_INDEXED = "indexed"
STATUS_FAILED = "failed"


@dataclass(frozen=True)
class PageText:
    """Cleaned text of one PDF page (1-based page number)."""

    page_number: int
    text: str


@dataclass(frozen=True)
class DocumentInfo:
    id: UUID
    name: str
    original_filename: str
    size_bytes: int
    page_count: int
    status: str
    chunk_count: int
    error_message: str | None
    is_sample: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class DocumentUploaded:
    """Domain event: a document was stored and is ready to be indexed by a subscriber."""

    document_id: UUID
    name: str
    pages: tuple[PageText, ...]


@dataclass(frozen=True)
class DocumentDeleted:
    """Domain event: a document was removed; subscribers must drop derived data."""

    document_id: UUID
