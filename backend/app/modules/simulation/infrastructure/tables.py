"""Table definitions owned by the simulation module (schema: simulation)."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

metadata = sa.MetaData(schema="simulation")
TZ = sa.DateTime(timezone=True)


def _id() -> sa.Column:
    return sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", TZ, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.text("now()")),
    ]


scenarios = sa.Table(
    "scenarios", metadata, _id(),
    sa.Column("key", sa.Text, nullable=False, unique=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("description", sa.Text, nullable=False),
    sa.Column("is_builtin", sa.Boolean, nullable=False),
    *_ts(),
)

scenario_parameters = sa.Table(
    "scenario_parameters", metadata, _id(),
    sa.Column("scenario_id", sa.Uuid, sa.ForeignKey("simulation.scenarios.id", ondelete="CASCADE"), nullable=False),
    sa.Column("parameters", pg.JSONB, nullable=False),
    sa.Column("is_default", sa.Boolean, nullable=False),
    *_ts(),
)

scenario_runs = sa.Table(
    "scenario_runs", metadata, _id(),
    sa.Column("scenario_id", sa.Uuid, sa.ForeignKey("simulation.scenarios.id", ondelete="SET NULL")),
    sa.Column("scenario_key", sa.Text, nullable=False),
    sa.Column("scenario_name", sa.Text, nullable=False),
    sa.Column("trigger", sa.Text, nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("data_version", sa.Integer),
    sa.Column("parameters", pg.JSONB, nullable=False),
    sa.Column("validation", pg.JSONB),
    sa.Column("error", sa.Text),
    sa.Column("record_count", sa.Integer, nullable=False),
    sa.Column("duration_ms", sa.Integer, nullable=False),
    *_ts(),
)

data_state = sa.Table(
    "data_state", metadata,
    sa.Column("id", sa.SmallInteger, primary_key=True),
    sa.Column("data_version", sa.Integer, nullable=False),
    sa.Column("scenario_key", sa.Text),
    sa.Column("scenario_name", sa.Text),
    sa.Column("last_run_id", sa.Uuid),
    sa.Column("applied_at", TZ),
    *_ts(),
)
