import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.ai_orchestration.infrastructure.demo_models import DemoRunRow


class DemoRunRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def current_session_id(self) -> uuid.UUID | None:
        """The demo session in progress = the session of the newest saved run (None when nothing is saved)."""
        return self._s.scalar(select(DemoRunRow.session_id).order_by(DemoRunRow.created_at.desc()).limit(1))

    def runs(self, session_id: uuid.UUID) -> list[DemoRunRow]:
        stmt = select(DemoRunRow).where(DemoRunRow.session_id == session_id).order_by(DemoRunRow.run_number)
        return list(self._s.scalars(stmt))

    def latest(self) -> DemoRunRow | None:
        return self._s.scalar(select(DemoRunRow).order_by(DemoRunRow.created_at.desc()).limit(1))

    def add(self, **fields) -> DemoRunRow:
        row = DemoRunRow(**fields)
        self._s.add(row)
        self._s.flush()
        self._s.refresh(row)
        return row

    def clear(self) -> int:
        return self._s.execute(delete(DemoRunRow)).rowcount or 0
