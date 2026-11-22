import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.ai_orchestration.infrastructure.models import AnalysisRunRow, ChatMessageRow, ChatSessionRow


class RunRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, **fields) -> AnalysisRunRow:
        row = AnalysisRunRow(**fields)
        self._s.add(row)
        self._s.flush()
        self._s.refresh(row)
        return row

    def get(self, run_id: uuid.UUID) -> AnalysisRunRow | None:
        return self._s.get(AnalysisRunRow, run_id)

    def list(self, *, limit: int, offset: int, run_type: str | None, scenario_key: str | None,
             data_version: int | None) -> tuple[list[AnalysisRunRow], int]:
        stmt = select(AnalysisRunRow)
        if run_type:
            stmt = stmt.where(AnalysisRunRow.run_type == run_type)
        if scenario_key:
            stmt = stmt.where(AnalysisRunRow.scenario_key == scenario_key)
        if data_version is not None:
            stmt = stmt.where(AnalysisRunRow.data_version == data_version)
        total = self._s.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = self._s.scalars(stmt.order_by(AnalysisRunRow.created_at.desc()).limit(limit).offset(offset))
        return list(rows), total


class ChatRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def create_session(self, title: str, owner: str) -> ChatSessionRow:
        row = ChatSessionRow(title=title, created_by=owner)
        self._s.add(row)
        self._s.flush()
        self._s.refresh(row)
        return row

    def list_sessions(self, owner: str, limit: int, offset: int) -> list[ChatSessionRow]:
        stmt = (
            select(ChatSessionRow).where(ChatSessionRow.created_by == owner)
            .order_by(ChatSessionRow.updated_at.desc()).limit(limit).offset(offset)
        )
        return list(self._s.scalars(stmt))

    def get_session(self, session_id: uuid.UUID, owner: str) -> ChatSessionRow | None:
        row = self._s.get(ChatSessionRow, session_id)
        return row if row is not None and row.created_by == owner else None

    def messages(self, session_id: uuid.UUID, limit: int | None = None) -> list[ChatMessageRow]:
        stmt = select(ChatMessageRow).where(ChatMessageRow.session_id == session_id)
        if limit is None:
            return list(self._s.scalars(stmt.order_by(ChatMessageRow.created_at)))
        newest = list(self._s.scalars(stmt.order_by(ChatMessageRow.created_at.desc()).limit(limit)))
        return list(reversed(newest))

    def add_message(self, **fields) -> ChatMessageRow:
        row = ChatMessageRow(**fields)
        self._s.add(row)
        self._s.flush()
        self._s.refresh(row)
        session = self._s.get(ChatSessionRow, row.session_id)
        if session is not None:
            session.updated_at = func.now()
        return row
