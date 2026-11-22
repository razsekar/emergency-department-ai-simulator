"""Simulation data: resource_management, patient_queue and simulation tables.

Revision ID: 0100
Revises: 0001
Branch: sim
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0100"
down_revision = "0001"
branch_labels = ("sim",)
depends_on = None


def _id() -> sa.Column:
    return sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    # ---- resource_management -------------------------------------------------
    op.create_table(
        "departments",
        _id(),
        sa.Column("code", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("capacity", sa.Integer, nullable=False, server_default="0"),
        sa.Column("workload_weight", sa.Float, nullable=False, server_default="1"),
        *_ts(),
        schema="resource_management",
    )
    op.create_table(
        "staff",
        _id(),
        sa.Column("ref", sa.Text, nullable=False, unique=True),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("department_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        *_ts(),
        sa.ForeignKeyConstraint(["department_id"], ["resource_management.departments.id"]),
        sa.CheckConstraint("role in ('doctor','nurse')", name="ck_staff_role"),
        sa.CheckConstraint("status in ('available','busy','off_duty')", name="ck_staff_status"),
        schema="resource_management",
    )
    op.create_index("ix_staff_dept_role_status", "staff", ["department_id", "role", "status"], schema="resource_management")
    op.create_table(
        "beds",
        _id(),
        sa.Column("ref", sa.Text, nullable=False, unique=True),
        sa.Column("department_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        *_ts(),
        sa.ForeignKeyConstraint(["department_id"], ["resource_management.departments.id"]),
        sa.CheckConstraint("status in ('available','occupied')", name="ck_beds_status"),
        schema="resource_management",
    )
    op.create_index("ix_beds_dept_status", "beds", ["department_id", "status"], schema="resource_management")
    op.create_table(
        "investigation_facilities",
        _id(),
        sa.Column("code", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("capacity", sa.Integer, nullable=False),
        sa.Column("expected_minutes", sa.Integer, nullable=False),
        *_ts(),
        schema="resource_management",
    )

    # ---- patient_queue -------------------------------------------------------
    op.create_table(
        "patient_visits",
        _id(),
        sa.Column("visit_ref", sa.Text, nullable=False, unique=True),
        sa.Column("patient_ref", sa.Text, nullable=False),
        sa.Column("arrival_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True)),
        sa.Column("department_code", sa.Text, nullable=False),
        sa.Column("triage_category", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("treatment_started_at", sa.DateTime(timezone=True)),
        sa.Column("assigned_staff_ref", sa.Text),
        sa.Column("bed_ref", sa.Text),
        sa.Column("discharged_at", sa.DateTime(timezone=True)),
        *_ts(),
        sa.CheckConstraint("status in ('waiting','in_treatment','discharged')", name="ck_visit_status"),
        sa.CheckConstraint(
            "triage_category in ('critical','urgent','semi_urgent','non_urgent')", name="ck_visit_triage"
        ),
        schema="patient_queue",
    )
    op.create_index("ix_visits_status", "patient_visits", ["status"], schema="patient_queue")
    op.create_index("ix_visits_department", "patient_visits", ["department_code"], schema="patient_queue")
    op.create_index("ix_visits_arrival", "patient_visits", ["arrival_at"], schema="patient_queue")
    op.create_index("ix_visits_triage", "patient_visits", ["triage_category"], schema="patient_queue")
    op.create_table(
        "investigation_requests",
        _id(),
        sa.Column("visit_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("facility_code", sa.Text, nullable=False),
        sa.Column("investigation_type", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("expected_minutes", sa.Integer, nullable=False),
        *_ts(),
        sa.ForeignKeyConstraint(["visit_id"], ["patient_queue.patient_visits.id"], ondelete="CASCADE"),
        sa.CheckConstraint("status in ('pending','completed')", name="ck_inv_status"),
        schema="patient_queue",
    )
    op.create_index("ix_inv_status", "investigation_requests", ["status"], schema="patient_queue")
    op.create_index("ix_inv_visit", "investigation_requests", ["visit_id"], schema="patient_queue")
    op.create_index("ix_inv_facility", "investigation_requests", ["facility_code"], schema="patient_queue")
    op.create_table(
        "dataset_clock",
        sa.Column("id", sa.SmallInteger, primary_key=True, server_default="1"),
        sa.Column("reference_time", sa.DateTime(timezone=True), nullable=False),
        *_ts(),
        sa.CheckConstraint("id = 1", name="ck_clock_singleton"),
        schema="patient_queue",
    )

    # ---- simulation ----------------------------------------------------------
    op.create_table(
        "scenarios",
        _id(),
        sa.Column("key", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("is_builtin", sa.Boolean, nullable=False, server_default=sa.text("true")),
        *_ts(),
        schema="simulation",
    )
    op.create_table(
        "scenario_parameters",
        _id(),
        sa.Column("scenario_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("parameters", pg.JSONB, nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("true")),
        *_ts(),
        sa.ForeignKeyConstraint(["scenario_id"], ["simulation.scenarios.id"], ondelete="CASCADE"),
        schema="simulation",
    )
    op.create_index("ix_scenario_parameters_scenario", "scenario_parameters", ["scenario_id"], schema="simulation")
    op.create_table(
        "scenario_runs",
        _id(),
        sa.Column("scenario_id", pg.UUID(as_uuid=True)),
        sa.Column("scenario_key", sa.Text, nullable=False),
        sa.Column("scenario_name", sa.Text, nullable=False),
        sa.Column("trigger", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("data_version", sa.Integer),
        sa.Column("parameters", pg.JSONB, nullable=False),
        sa.Column("validation", pg.JSONB),
        sa.Column("error", sa.Text),
        sa.Column("record_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
        *_ts(),
        sa.ForeignKeyConstraint(["scenario_id"], ["simulation.scenarios.id"], ondelete="SET NULL"),
        sa.CheckConstraint("status in ('applied','failed')", name="ck_run_status"),
        schema="simulation",
    )
    op.create_index("ix_scenario_runs_created", "scenario_runs", ["created_at"], schema="simulation")
    op.create_table(
        "data_state",
        sa.Column("id", sa.SmallInteger, primary_key=True, server_default="1"),
        sa.Column("data_version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("scenario_key", sa.Text),
        sa.Column("scenario_name", sa.Text),
        sa.Column("last_run_id", pg.UUID(as_uuid=True)),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        *_ts(),
        sa.CheckConstraint("id = 1", name="ck_data_state_singleton"),
        schema="simulation",
    )
    op.execute("INSERT INTO simulation.data_state (id, data_version) VALUES (1, 0)")


def downgrade() -> None:
    for table, schema in [
        ("data_state", "simulation"),
        ("scenario_runs", "simulation"),
        ("scenario_parameters", "simulation"),
        ("scenarios", "simulation"),
        ("dataset_clock", "patient_queue"),
        ("investigation_requests", "patient_queue"),
        ("patient_visits", "patient_queue"),
        ("investigation_facilities", "resource_management"),
        ("beds", "resource_management"),
        ("staff", "resource_management"),
        ("departments", "resource_management"),
    ]:
        op.drop_table(table, schema=schema)
