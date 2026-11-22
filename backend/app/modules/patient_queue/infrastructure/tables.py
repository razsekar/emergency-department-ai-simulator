"""Table definitions owned by the patient_queue module (schema: patient_queue)."""
import sqlalchemy as sa

metadata = sa.MetaData(schema="patient_queue")


def _id() -> sa.Column:
    return sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


TZ = sa.DateTime(timezone=True)

visits = sa.Table(
    "patient_visits",
    metadata,
    _id(),
    sa.Column("visit_ref", sa.Text, nullable=False, unique=True),
    sa.Column("patient_ref", sa.Text, nullable=False),
    sa.Column("arrival_at", TZ, nullable=False),
    sa.Column("registered_at", TZ),
    sa.Column("department_code", sa.Text, nullable=False),
    sa.Column("triage_category", sa.Text, nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("treatment_started_at", TZ),
    sa.Column("assigned_staff_ref", sa.Text),
    sa.Column("bed_ref", sa.Text),
    sa.Column("discharged_at", TZ),
    *_ts(),
)

investigations = sa.Table(
    "investigation_requests",
    metadata,
    _id(),
    sa.Column("visit_id", sa.Uuid, sa.ForeignKey("patient_queue.patient_visits.id", ondelete="CASCADE"),
              nullable=False),
    sa.Column("facility_code", sa.Text, nullable=False),
    sa.Column("investigation_type", sa.Text, nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("requested_at", TZ, nullable=False),
    sa.Column("completed_at", TZ),
    sa.Column("expected_minutes", sa.Integer, nullable=False),
    *_ts(),
)

dataset_clock = sa.Table(
    "dataset_clock",
    metadata,
    sa.Column("id", sa.SmallInteger, primary_key=True, server_default="1"),
    sa.Column("reference_time", TZ, nullable=False),
    *_ts(),
)
