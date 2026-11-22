import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.ai_orchestration.infrastructure.comparison_models import ComparisonResultRow, ComparisonRunRow


class ComparisonRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, run_fields: dict, results: list[dict]) -> tuple[ComparisonRunRow, list[ComparisonResultRow]]:
        run = ComparisonRunRow(**run_fields)
        self._s.add(run)
        self._s.flush()
        rows = [ComparisonResultRow(comparison_id=run.id, **r) for r in results]
        self._s.add_all(rows)
        self._s.flush()
        self._s.refresh(run)
        for row in rows:
            self._s.refresh(row)
        return run, sorted(rows, key=lambda r: r.position)

    def get(self, comparison_id: uuid.UUID) -> tuple[ComparisonRunRow, list[ComparisonResultRow]] | None:
        run = self._s.get(ComparisonRunRow, comparison_id)
        if run is None:
            return None
        rows = self._s.scalars(
            select(ComparisonResultRow).where(ComparisonResultRow.comparison_id == comparison_id)
            .order_by(ComparisonResultRow.position)
        )
        return run, list(rows)

    def list(self, *, limit: int, offset: int, data_version: int | None
             ) -> tuple[list[tuple[ComparisonRunRow, list[str]]], int]:
        stmt = select(ComparisonRunRow)
        if data_version is not None:
            stmt = stmt.where(ComparisonRunRow.data_version == data_version)
        total = self._s.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        runs = list(self._s.scalars(stmt.order_by(ComparisonRunRow.created_at.desc()).limit(limit).offset(offset)))
        out: list[tuple[ComparisonRunRow, list[str]]] = []
        for run in runs:
            models = self._s.execute(
                select(ComparisonResultRow.provider, ComparisonResultRow.model)
                .where(ComparisonResultRow.comparison_id == run.id).order_by(ComparisonResultRow.position)
            ).all()
            out.append((run, [f"{p}/{m}" for p, m in models]))
        return out, total
