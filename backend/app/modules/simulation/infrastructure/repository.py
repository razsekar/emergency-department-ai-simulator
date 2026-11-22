"""Persistence for the simulation module."""
import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.modules.simulation.infrastructure.tables import data_state, scenario_parameters, scenario_runs, scenarios


def ensure_scenario(session: Session, key: str, name: str, description: str, is_builtin: bool,
                    default_params: dict | None) -> uuid.UUID:
    session.execute(
        pg_insert(scenarios)
        .values(key=key, name=name, description=description, is_builtin=is_builtin)
        .on_conflict_do_nothing(index_elements=["key"])
    )
    scenario_id = session.execute(sa.select(scenarios.c.id).where(scenarios.c.key == key)).scalar_one()
    if default_params is not None:
        exists = session.execute(
            sa.select(scenario_parameters.c.id).where(
                scenario_parameters.c.scenario_id == scenario_id, scenario_parameters.c.is_default.is_(True)
            )
        ).first()
        if not exists:
            session.execute(
                sa.insert(scenario_parameters).values(
                    scenario_id=scenario_id, parameters=default_params, is_default=True
                )
            )
    return scenario_id


def bump_version(session: Session, key: str, name: str, run_id: uuid.UUID, applied_at: datetime) -> int:
    """Atomically increment the data version (row lock serialises concurrent applies)."""
    return session.execute(
        sa.update(data_state)
        .where(data_state.c.id == 1)
        .values(
            data_version=data_state.c.data_version + 1, scenario_key=key, scenario_name=name,
            last_run_id=run_id, applied_at=applied_at, updated_at=sa.func.now(),
        )
        .returning(data_state.c.data_version)
    ).scalar_one()


def insert_run(session: Session, **values: Any) -> uuid.UUID:
    run_id = values.pop("id", None) or uuid.uuid4()
    session.execute(sa.insert(scenario_runs).values(id=run_id, **values))
    return run_id


def get_state(session: Session) -> sa.Row:
    return session.execute(sa.select(data_state).where(data_state.c.id == 1)).one()


def get_run(session: Session, run_id: uuid.UUID) -> sa.Row:
    return session.execute(sa.select(scenario_runs).where(scenario_runs.c.id == run_id)).one()


def list_runs(session: Session, limit: int, offset: int):
    total = session.execute(sa.select(sa.func.count()).select_from(scenario_runs)).scalar_one()
    rows = session.execute(
        sa.select(scenario_runs).order_by(scenario_runs.c.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return total, rows
