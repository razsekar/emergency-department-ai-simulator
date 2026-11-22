from uuid import UUID

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    k: int = Field(default=5, ge=1, le=20)


class ChunkOut(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_name: str
    page_number: int
    chunk_index: int
    excerpt: str
    score: float
    injection_flagged: bool
    injection_signals: list[str]


class SearchResponse(BaseModel):
    query: str
    embedding_model: str
    results: list[ChunkOut]
    llm_context: str = Field(description="Delimited, untrusted-data context block for LLM prompts")
