"""AI model comparison runs (ai_orchestration schema).

Revision ID: 0600
Revises: 0001

One comparison run freezes ONE scenario snapshot, ONE set of tool results and ONE retrieved policy context; each
selected model then answers from that identical context. Per-model results live in a child table (FK inside the
schema only). Scenario/data-version values are opaque copies, never cross-schema foreign keys.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0600"
down_revision = "0001"
branch_labels = ("comparison",)
depends_on = None

NOW = sa.text("now()")


def _ts(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=NOW)


def upgrade() -> None:
    op.create_table(
        "ai_comparison_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("scenario_key", sa.String(64), nullable=True),
        sa.Column("scenario_name", sa.String(128), nullable=True),
        sa.Column("data_version", sa.Integer, nullable=True),
        sa.Column("data_version_consistent", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("snapshot_metrics", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("shared_tools", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("shared_policies", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("context_sha256", sa.String(64), nullable=False),
        sa.Column("selections", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(16), nullable=False),  # completed | partial | failed
        sa.Column("created_by", sa.String(128), nullable=False, server_default="system"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint("status IN ('completed','partial','failed')", name="ck_ai_comparison_status"),
        schema="ai_orchestration",
    )
    op.create_index("ix_ai_comparison_created", "ai_comparison_runs", ["created_at"], schema="ai_orchestration")
    op.create_index("ix_ai_comparison_version", "ai_comparison_runs", ["data_version"], schema="ai_orchestration")

    op.create_table(
        "ai_comparison_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "comparison_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_orchestration.ai_comparison_runs.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("temperature", sa.Float, nullable=True),
        sa.Column("status", sa.String(16), nullable=False),  # completed | failed | not_configured
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("answer", sa.Text, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("prompt_tokens", sa.Integer, nullable=True),
        sa.Column("completion_tokens", sa.Integer, nullable=True),
        sa.Column("total_tokens", sa.Integer, nullable=True),
        sa.Column("estimated_cost_usd", sa.Float, nullable=True),
        sa.Column("tool_calling_supported", sa.Boolean, nullable=True),
        sa.Column("data_disclosure", sa.Text, nullable=True),
        sa.Column("context_sha256", sa.String(64), nullable=True),
        sa.Column("scores", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("citation_check", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        _ts("created_at"),
        sa.CheckConstraint("status IN ('completed','failed','not_configured')", name="ck_ai_comparison_result_status"),
        sa.UniqueConstraint("comparison_id", "position", name="uq_ai_comparison_result_position"),
        schema="ai_orchestration",
    )
    op.create_index("ix_ai_comparison_results_run", "ai_comparison_results", ["comparison_id"], schema="ai_orchestration")


def downgrade() -> None:
    op.drop_table("ai_comparison_results", schema="ai_orchestration")
    op.drop_table("ai_comparison_runs", schema="ai_orchestration")
