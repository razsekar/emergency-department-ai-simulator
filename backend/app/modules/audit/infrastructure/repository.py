from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.infrastructure.models import AuditEventRow


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add_event(self, **fields) -> AuditEventRow:
        row = AuditEventRow(**fields)
        self._s.add(row)
        self._s.flush()
        return row

    def list_events(
        self, *, limit: int, offset: int, action: str | None, actor: str | None, outcome: str | None
    ) -> tuple[list[AuditEventRow], int]:
        stmt = select(AuditEventRow)
        if action:
            stmt = stmt.where(AuditEventRow.action.startswith(action, autoescape=True))
        if actor:
            stmt = stmt.where(AuditEventRow.actor == actor)
        if outcome:
            stmt = stmt.where(AuditEventRow.outcome == outcome)
        total = self._s.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = self._s.scalars(
            stmt.order_by(AuditEventRow.occurred_at.desc(), AuditEventRow.id).limit(limit).offset(offset)
        )
        return list(rows), total
