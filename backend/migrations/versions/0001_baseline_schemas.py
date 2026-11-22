"""Baseline: pgvector extension and one PostgreSQL schema per module.

Revision ID: 0001
Revises:
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

MODULE_SCHEMAS = [
    "identity", "simulation", "patient_queue", "resource_management", "analytics",
    "knowledge_base", "rag", "ai_orchestration", "agent_tools", "model_providers", "audit",
]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    for schema in MODULE_SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")


def downgrade() -> None:
    for schema in reversed(MODULE_SCHEMAS):
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
