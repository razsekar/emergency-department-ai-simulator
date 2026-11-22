"""Demonstration-mode runs (Run 1/2/3 of the fixed question across scenarios).

Revision ID: 0700
Revises: 0001

analysis_run_id links to ai_orchestration.analysis_runs by value only (opaque UUID, no foreign key) so this
migration branch is independent of the `agent` branch.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0700"
down_revision = "0001"
branch_labels = ("demo",)
depends_on = None

NOW = sa.text("now()")


def _ts(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=NOW)


def upgrade() -> None:
    op.create_table(
        "demo_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_number", sa.Integer, nullable=False),
        sa.Column("run_label", sa.String(16), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scenario_key", sa.String(64), nullable=True),
        sa.Column("scenario_name", sa.String(128), nullable=True),
        sa.Column("data_version", sa.Integer, nullable=False),
        sa.Column("patient_record_count", sa.Integer, nullable=False),
        sa.Column("metrics_snapshot", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("verification", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("tools_executed", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("retrieved_policies", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("question_sha256", sa.String(64), nullable=False),
        sa.Column("final_answer", sa.Text, nullable=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("prompt_tokens", sa.Integer, nullable=True),
        sa.Column("completion_tokens", sa.Integer, nullable=True),
        sa.Column("total_tokens", sa.Integer, nullable=True),
        sa.Column("estimated_cost_usd", sa.Float, nullable=True),
        sa.Column("created_by", sa.String(128), nullable=False, server_default="system"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.UniqueConstraint("session_id", "run_number", name="uq_demo_runs_session_number"),
        schema="ai_orchestration",
    )
    op.create_index("ix_demo_runs_session", "demo_runs", ["session_id", "run_number"], schema="ai_orchestration")
    op.create_index("ix_demo_runs_created", "demo_runs", ["created_at"], schema="ai_orchestration")


def downgrade() -> None:
    op.drop_table("demo_runs", schema="ai_orchestration")
