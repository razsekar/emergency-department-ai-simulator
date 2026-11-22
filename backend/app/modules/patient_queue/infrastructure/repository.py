"""Persistence for patient_queue. All waiting durations are measured against the dataset clock
(the reference time stored when the dataset was generated), so they stay stable until the
next scenario is applied."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.patient_queue.infrastructure.tables import TZ, dataset_clock, investigations, visits


def reference_time(session: Session) -> datetime | None:
    return session.execute(sa.select(dataset_clock.c.reference_time)).scalar_one_or_none()


def effective_reference(session: Session) -> datetime:
    return reference_time(session) or datetime.now(timezone.utc)


def replace_dataset(session: Session, spec: Any) -> None:
    session.execute(sa.delete(investigations))
    session.execute(sa.delete(visits))
    session.execute(sa.delete(dataset_clock))
    session.execute(sa.insert(dataset_clock), [{"id": 1, "reference_time": spec.reference_time}])
    ids = {v.visit_ref: uuid.uuid4() for v in spec.visits}
    if spec.visits:
        session.execute(
            sa.insert(visits),
            [{"id": ids[v.visit_ref], **v.model_dump()} for v in spec.visits],
        )
    unknown = [i.visit_ref for i in spec.investigations if i.visit_ref not in ids]
    if unknown:
        raise ValueError(f"investigation requests reference unknown visits: {unknown[:3]}")
    if spec.investigations:
        session.execute(
            sa.insert(investigations),
            [
                {"visit_id": ids[i.visit_ref], **i.model_dump(exclude={"visit_ref"})}
                for i in spec.investigations
            ],
        )


def _wait_minutes(ref: datetime) -> sa.ColumnElement:
    ref_lit = sa.literal(ref, TZ)
    seconds = sa.extract("epoch", sa.func.coalesce(visits.c.treatment_started_at, ref_lit) - visits.c.arrival_at)
    return sa.cast(seconds, sa.Float) / 60.0


def _investigation_status() -> sa.ColumnElement:
    pending = sa.exists().where(investigations.c.visit_id == visits.c.id, investigations.c.status == "pending")
    completed = sa.exists().where(investigations.c.visit_id == visits.c.id, investigations.c.status == "completed")
    return sa.case((pending, "pending"), (completed, "completed"), else_="none")


def query_queue(session: Session, f: Any, limit: int, offset: int):
    ref = effective_reference(session)
    wait = _wait_minutes(ref).label("waiting_minutes")
    inv = _investigation_status().label("investigation_status")
    base = sa.select(
        visits.c.visit_ref, visits.c.patient_ref, visits.c.arrival_at, visits.c.registered_at,
        visits.c.department_code, visits.c.triage_category, visits.c.status, visits.c.assigned_staff_ref,
        visits.c.bed_ref, visits.c.discharged_at, wait, inv,
    )
    if f.status:
        base = base.where(visits.c.status == f.status)
    if f.department_code:
        base = base.where(visits.c.department_code == f.department_code)
    if f.triage_category:
        base = base.where(visits.c.triage_category == f.triage_category)
    if f.arrived_within_minutes is not None:
        base = base.where(visits.c.arrival_at >= ref - timedelta(minutes=f.arrived_within_minutes))
    if f.min_wait_minutes is not None:
        base = base.where(_wait_minutes(ref) >= f.min_wait_minutes)
    if f.max_wait_minutes is not None:
        base = base.where(_wait_minutes(ref) <= f.max_wait_minutes)
    if f.investigation_status:
        base = base.where(_investigation_status() == f.investigation_status)
    total = session.execute(sa.select(sa.func.count()).select_from(base.subquery())).scalar_one()
    rows = session.execute(base.order_by(visits.c.arrival_at, visits.c.visit_ref).limit(limit).offset(offset)).all()
    return ref, total, rows


def visit_counts(session: Session):
    row = session.execute(
        sa.select(
            sa.func.count(visits.c.id),
            sa.func.count(visits.c.id).filter(visits.c.status == "waiting"),
            sa.func.count(visits.c.id).filter(visits.c.status == "in_treatment"),
            sa.func.count(visits.c.id).filter(visits.c.status == "discharged"),
            sa.func.count(visits.c.id).filter(
                visits.c.triage_category == "critical", visits.c.status != "discharged"
            ),
        )
    ).one()
    return reference_time(session), row


def waiting_minutes_list(session: Session, department_code: str | None, window_minutes: int | None) -> tuple[datetime, list[float]]:
    ref = effective_reference(session)
    q = sa.select(_wait_minutes(ref)).where(visits.c.status == "waiting")
    if department_code:
        q = q.where(visits.c.department_code == department_code)
    if window_minutes is not None:
        q = q.where(visits.c.arrival_at >= ref - timedelta(minutes=window_minutes))
    return ref, [float(x) for x in session.execute(q).scalars()]


def pending_investigations(session: Session, department_code: str | None):
    ref = effective_reference(session)
    q = (
        sa.select(
            visits.c.visit_ref, visits.c.patient_ref, visits.c.department_code, investigations.c.facility_code,
            investigations.c.requested_at, investigations.c.expected_minutes,
        )
        .select_from(investigations.join(visits, investigations.c.visit_id == visits.c.id))
        .where(investigations.c.status == "pending")
        .order_by(investigations.c.requested_at, visits.c.visit_ref)
    )
    if department_code:
        q = q.where(visits.c.department_code == department_code)
    return ref, session.execute(q).all()


def arrival_times(session: Session, since: datetime) -> list[datetime]:
    return list(session.execute(sa.select(visits.c.arrival_at).where(visits.c.arrival_at >= since)).scalars())


def workload_by_department(session: Session) -> list[sa.Row]:
    pending = (
        sa.select(visits.c.department_code.label("code"), sa.func.count(investigations.c.id).label("pending"))
        .select_from(investigations.join(visits, investigations.c.visit_id == visits.c.id))
        .where(investigations.c.status == "pending")
        .group_by(visits.c.department_code)
        .subquery()
    )
    q = (
        sa.select(
            visits.c.department_code,
            sa.func.count(visits.c.id).filter(visits.c.status == "waiting").label("waiting"),
            sa.func.count(visits.c.id).filter(visits.c.status == "in_treatment").label("in_treatment"),
            sa.func.coalesce(sa.func.max(pending.c.pending), 0).label("pending"),
        )
        .select_from(visits.outerjoin(pending, pending.c.code == visits.c.department_code))
        .group_by(visits.c.department_code)
        .order_by(visits.c.department_code)
    )
    return list(session.execute(q))
