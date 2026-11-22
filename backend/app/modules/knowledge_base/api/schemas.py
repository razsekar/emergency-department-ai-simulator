from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DocumentOut(BaseModel):
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


class DocumentPage(BaseModel):
    items: list[DocumentOut]
    total: int
    limit: int
    offset: int


class SampleLoadResult(BaseModel):
    loaded: list[str]
    skipped: list[str]
