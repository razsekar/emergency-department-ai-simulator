"""Persistence for rag.document_chunks (owned exclusively by this module)."""
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"


@dataclass(frozen=True)
class NewChunk:
    page_number: int
    chunk_index: int
    content: str
    embedding: list[float]
    injection_flagged: bool
    injection_signals: tuple[str, ...]


@dataclass(frozen=True)
class ChunkHit:
    chunk_id: UUID
    document_id: UUID
    document_name: str
    page_number: int
    chunk_index: int
    content: str
    injection_flagged: bool
    injection_signals: list[str]
    score: float


class ChunkRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def replace_document_chunks(self, document_id: UUID, document_name: str, chunks: list[NewChunk]) -> int:
        self.delete_document_chunks(document_id)
        for c in chunks:
            self.s.execute(
                text(
                    "INSERT INTO rag.document_chunks (document_id, document_name, page_number, chunk_index, "
                    "content, injection_flagged, injection_signals, embedding) "
                    "VALUES (:doc, :name, :page, :idx, :content, :flag, :signals, CAST(:emb AS vector))"
                ),
                {"doc": document_id, "name": document_name, "page": c.page_number, "idx": c.chunk_index,
                 "content": c.content, "flag": c.injection_flagged, "signals": list(c.injection_signals),
                 "emb": vector_literal(c.embedding)},
            )
        return len(chunks)

    def delete_document_chunks(self, document_id: UUID) -> int:
        res = self.s.execute(text("DELETE FROM rag.document_chunks WHERE document_id = :d"), {"d": document_id})
        return res.rowcount

    def search(self, query_embedding: list[float], k: int) -> list[ChunkHit]:
        rows = self.s.execute(
            text(
                "SELECT id, document_id, document_name, page_number, chunk_index, content, "
                "injection_flagged, injection_signals, "
                "1 - (embedding <=> CAST(:q AS vector)) AS score "
                "FROM rag.document_chunks "
                "ORDER BY embedding <=> CAST(:q AS vector) LIMIT :k"
            ),
            {"q": vector_literal(query_embedding), "k": k},
        ).all()
        return [
            ChunkHit(r.id, r.document_id, r.document_name, r.page_number, r.chunk_index, r.content,
                     r.injection_flagged, list(r.injection_signals), float(r.score))
            for r in rows
        ]

    def count(self) -> int:
        return self.s.execute(text("SELECT count(*) FROM rag.document_chunks")).scalar_one()
