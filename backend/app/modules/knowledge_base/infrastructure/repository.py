"""Persistence for knowledge_base.knowledge_documents (owned exclusively by this module)."""
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.knowledge_base.domain.models import DocumentInfo

_COLS = (
    "id, name, original_filename, size_bytes, page_count, status, chunk_count, "
    "error_message, is_sample, created_at, updated_at"
)


def _to_info(row) -> DocumentInfo:
    return DocumentInfo(**row._mapping)


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def insert(
        self, *, name: str, original_filename: str, sha256: str, size_bytes: int,
        page_count: int, is_sample: bool,
    ) -> DocumentInfo:
        row = self.s.execute(
            text(
                f"INSERT INTO knowledge_base.knowledge_documents "
                f"(name, original_filename, content_sha256, size_bytes, page_count, is_sample) "
                f"VALUES (:name, :fn, :sha, :size, :pages, :sample) RETURNING {_COLS}"
            ),
            {"name": name, "fn": original_filename, "sha": sha256, "size": size_bytes,
             "pages": page_count, "sample": is_sample},
        ).one()
        return _to_info(row)

    def find_by_sha256(self, sha256: str) -> DocumentInfo | None:
        row = self.s.execute(
            text(f"SELECT {_COLS} FROM knowledge_base.knowledge_documents WHERE content_sha256 = :sha"),
            {"sha": sha256},
        ).first()
        return _to_info(row) if row else None

    def get(self, document_id: UUID) -> DocumentInfo | None:
        row = self.s.execute(
            text(f"SELECT {_COLS} FROM knowledge_base.knowledge_documents WHERE id = :id"),
            {"id": document_id},
        ).first()
        return _to_info(row) if row else None

    def list(self, limit: int, offset: int) -> list[DocumentInfo]:
        rows = self.s.execute(
            text(
                f"SELECT {_COLS} FROM knowledge_base.knowledge_documents "
                f"ORDER BY created_at DESC, name LIMIT :limit OFFSET :offset"
            ),
            {"limit": limit, "offset": offset},
        ).all()
        return [_to_info(r) for r in rows]

    def count(self) -> int:
        return self.s.execute(text("SELECT count(*) FROM knowledge_base.knowledge_documents")).scalar_one()

    def set_status(self, document_id: UUID, status: str, chunk_count: int, error: str | None) -> bool:
        res = self.s.execute(
            text(
                "UPDATE knowledge_base.knowledge_documents "
                "SET status = :status, chunk_count = :cc, error_message = :err, updated_at = now() "
                "WHERE id = :id"
            ),
            {"status": status, "cc": chunk_count, "err": error, "id": document_id},
        )
        return res.rowcount == 1

    def delete(self, document_id: UUID) -> bool:
        res = self.s.execute(
            text("DELETE FROM knowledge_base.knowledge_documents WHERE id = :id"), {"id": document_id}
        )
        return res.rowcount == 1
