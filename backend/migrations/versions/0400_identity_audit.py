"""Identity (users, roles, permissions) and audit (audit_events) tables, with RBAC reference data.

Revision ID: 0400
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0400"
down_revision = "0001"
branch_labels = ("identity",)
depends_on = None

UUID_PK = dict(primary_key=True, server_default=sa.text("gen_random_uuid()"))
NOW = sa.text("now()")

# Literal copy of the reference matrix (domain/permissions.py); a test asserts they stay in sync.
VIEWER = ["dashboard:read", "queue:read", "resources:read", "scenario:read", "knowledge:read", "models:read"]
PRESENTER = VIEWER + ["scenario:apply", "scenario:reset", "knowledge:upload", "ai:chat", "agent:run",
                      "comparison:run"]
ADMIN = PRESENTER + ["models:configure", "audit:read"]
ROLES = {"viewer": VIEWER, "presenter": PRESENTER, "admin": ADMIN}


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), **UUID_PK),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        schema="identity",
    )
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), **UUID_PK),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        schema="identity",
    )
    op.create_table(
        "permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), **UUID_PK),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        schema="identity",
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("identity.users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("identity.roles.id", ondelete="CASCADE"), primary_key=True),
        schema="identity",
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("identity.roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("identity.permissions.id", ondelete="CASCADE"), primary_key=True),
        schema="identity",
    )
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), **UUID_PK),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource", sa.String(255), nullable=True),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("detail", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint("outcome IN ('success','failure','denied')", name="ck_audit_events_outcome"),
        schema="audit",
    )
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"], schema="audit")
    op.create_index("ix_audit_events_action", "audit_events", ["action"], schema="audit")
    op.create_index("ix_audit_events_actor", "audit_events", ["actor"], schema="audit")

    bind = op.get_bind()
    for code in sorted(set(ADMIN)):
        bind.execute(sa.text("INSERT INTO identity.permissions (code) VALUES (:c)"), {"c": code})
    for role, perms in ROLES.items():
        bind.execute(sa.text("INSERT INTO identity.roles (name) VALUES (:r)"), {"r": role})
        for code in perms:
            bind.execute(
                sa.text(
                    "INSERT INTO identity.role_permissions (role_id, permission_id) "
                    "SELECT r.id, p.id FROM identity.roles r, identity.permissions p "
                    "WHERE r.name = :r AND p.code = :c"
                ),
                {"r": role, "c": code},
            )


def downgrade() -> None:
    op.drop_table("audit_events", schema="audit")
    op.drop_table("role_permissions", schema="identity")
    op.drop_table("user_roles", schema="identity")
    op.drop_table("permissions", schema="identity")
    op.drop_table("roles", schema="identity")
    op.drop_table("users", schema="identity")
