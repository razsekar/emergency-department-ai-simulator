"""Table definitions owned by the resource_management module (schema: resource_management)."""
import sqlalchemy as sa

metadata = sa.MetaData(schema="resource_management")


def _id() -> sa.Column:
    return sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


departments = sa.Table(
    "departments",
    metadata,
    _id(),
    sa.Column("code", sa.Text, nullable=False, unique=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("capacity", sa.Integer, nullable=False),
    sa.Column("workload_weight", sa.Float, nullable=False),
    *_ts(),
)

staff = sa.Table(
    "staff",
    metadata,
    _id(),
    sa.Column("ref", sa.Text, nullable=False, unique=True),
    sa.Column("role", sa.Text, nullable=False),
    sa.Column("department_id", sa.Uuid, sa.ForeignKey("resource_management.departments.id"), nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    *_ts(),
)

beds = sa.Table(
    "beds",
    metadata,
    _id(),
    sa.Column("ref", sa.Text, nullable=False, unique=True),
    sa.Column("department_id", sa.Uuid, sa.ForeignKey("resource_management.departments.id"), nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    *_ts(),
)

facilities = sa.Table(
    "investigation_facilities",
    metadata,
    _id(),
    sa.Column("code", sa.Text, nullable=False, unique=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("capacity", sa.Integer, nullable=False),
    sa.Column("expected_minutes", sa.Integer, nullable=False),
    *_ts(),
)
