"""model_providers: model_configurations (no secrets; env var NAME references only).

Revision ID: 0300
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0300"
down_revision = "0001"
branch_labels = ("providers",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model_id", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("api_key_env_var", sa.String(128), nullable=True),
        sa.Column("api_base_env_var", sa.String(128), nullable=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "model_id", name="uq_model_configurations_provider_model"),
        sa.CheckConstraint("provider IN ('anthropic','openai','gemini','ollama')", name="ck_model_configurations_provider"),
        schema="model_providers",
    )
    op.create_index("ix_model_configurations_provider", "model_configurations", ["provider"], schema="model_providers")


def downgrade() -> None:
    op.drop_index("ix_model_configurations_provider", table_name="model_configurations", schema="model_providers")
    op.drop_table("model_configurations", schema="model_providers")
