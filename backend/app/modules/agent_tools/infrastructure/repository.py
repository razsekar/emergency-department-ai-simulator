import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.agent_tools.infrastructure.models import AgentExecutionLogRow


class ExecutionLogRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, **fields) -> AgentExecutionLogRow:
        row = AgentExecutionLogRow(**fields)
        self._s.add(row)
        self._s.flush()
        return row

    def list_for_run(self, run_id: uuid.UUID) -> list[AgentExecutionLogRow]:
        stmt = (
            select(AgentExecutionLogRow)
            .where(AgentExecutionLogRow.run_id == run_id)
            .order_by(AgentExecutionLogRow.sequence, AgentExecutionLogRow.created_at)
        )
        return list(self._s.scalars(stmt))
