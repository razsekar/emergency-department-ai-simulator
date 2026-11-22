"""Agent tool execution logs and AI orchestration (analysis runs, chat sessions and messages).

Revision ID: 0500
Revises: 0001

Cross-module references (run_id on agent_execution_logs) are opaque UUIDs, never cross-schema foreign keys.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0500"
down_revision = "0001"
branch_labels = ("agent",)
depends_on = None

UUID_PK = dict(primary_key=True, server_default=sa.text("gen_random_uuid()"))
NOW = sa.text("now()")


def _ts(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=NOW)


def upgrade() -> None:
    op.create_table(
        "agent_execution_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), **UUID_PK),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sequence", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("arguments", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result_summary", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("data_version", sa.Integer, nullable=True),
        _ts("created_at"),
        sa.CheckConstraint(
            "status IN ('ok','invalid_arguments','unknown_tool','error','refused')", name="ck_agent_log_status"
        ),
        schema="agent_tools",
    )
    op.create_index("ix_agent_logs_run", "agent_execution_logs", ["run_id", "sequence"], schema="agent_tools")
    op.create_index("ix_agent_logs_tool", "agent_execution_logs", ["tool_name", "created_at"], schema="agent_tools")

    op.create_table(
        "analysis_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), **UUID_PK),
        sa.Column("run_type", sa.String(16), nullable=False),  # agent | demo
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("scenario_key", sa.String(64), nullable=True),
        sa.Column("scenario_name", sa.String(128), nullable=True),
        sa.Column("data_version", sa.Integer, nullable=True),
        sa.Column("data_version_consistent", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("snapshot_metrics", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("mode", sa.String(16), nullable=False),  # native | fallback
        sa.Column("fallback_reason", sa.Text, nullable=True),
        sa.Column("tools_executed", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("retrieved_docs", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("citation_check", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("temperature", sa.Float, nullable=True),
        sa.Column("llm_calls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("prompt_tokens", sa.Integer, nullable=True),
        sa.Column("completion_tokens", sa.Integer, nullable=True),
        sa.Column("total_tokens", sa.Integer, nullable=True),
        sa.Column("estimated_cost_usd", sa.Float, nullable=True),
        sa.Column("data_disclosure", sa.Text, nullable=True),
        sa.Column("answer", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False),  # completed | failed
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(128), nullable=False, server_default="system"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint("run_type IN ('agent','demo')", name="ck_analysis_run_type"),
        sa.CheckConstraint("mode IN ('native','fallback')", name="ck_analysis_mode"),
        sa.CheckConstraint("status IN ('completed','failed')", name="ck_analysis_status"),
        schema="ai_orchestration",
    )
    op.create_index("ix_analysis_runs_created", "analysis_runs", ["created_at"], schema="ai_orchestration")
    op.create_index("ix_analysis_runs_version", "analysis_runs", ["data_version"], schema="ai_orchestration")
    op.create_index("ix_analysis_runs_type", "analysis_runs", ["run_type", "created_at"], schema="ai_orchestration")

    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), **UUID_PK),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        schema="ai_orchestration",
    )
    op.create_index("ix_chat_sessions_owner", "chat_sessions", ["created_by", "updated_at"], schema="ai_orchestration")

    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), **UUID_PK),
        sa.Column(
            "session_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_orchestration.chat_sessions.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("sources", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("citation_check", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("provider", sa.String(32), nullable=True),
        sa.Column("model", sa.String(255), nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("prompt_tokens", sa.Integer, nullable=True),
        sa.Column("completion_tokens", sa.Integer, nullable=True),
        sa.Column("data_disclosure", sa.Text, nullable=True),
        _ts("created_at"),
        sa.CheckConstraint("role IN ('user','assistant')", name="ck_chat_message_role"),
        schema="ai_orchestration",
    )
    op.create_index("ix_chat_messages_session", "chat_messages", ["session_id", "created_at"], schema="ai_orchestration")


def downgrade() -> None:
    op.drop_table("chat_messages", schema="ai_orchestration")
    op.drop_table("chat_sessions", schema="ai_orchestration")
    op.drop_table("analysis_runs", schema="ai_orchestration")
    op.drop_table("agent_execution_logs", schema="agent_tools")
