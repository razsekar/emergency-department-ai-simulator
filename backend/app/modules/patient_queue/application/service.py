"""Use cases of the patient_queue module."""
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, TypeVar

from sqlalchemy.orm import Session

from app.modules.patient_queue.application import contracts as c
from app.modules.patient_queue.infrastructure import repository as repo
from app.platform.db import unit_of_work

T = TypeVar("T")

# (label, min inclusive, max exclusive or None)
WAIT_BUCKETS: list[tuple[str, float, float | None]] = [
    ("0-15 min", 0, 15),
    ("15-30 min", 15, 30),
    ("30-60 min", 30, 60),
    ("60-90 min", 60, 90),
    ("90-120 min", 90, 120),
    ("120+ min", 120, None),
]


def run(fn: Callable[..., T], /, **kwargs: Any) -> T:
    """Execute a use case in its own transaction (used by API controllers)."""
    with unit_of_work() as session:
        return fn(session, **kwargs)


def replace_dataset(session: Session, spec: c.DatasetSpec) -> None:
    repo.replace_dataset(session, spec)


def get_reference_time(session: Session) -> datetime | None:
    return repo.reference_time(session)


def get_queue(session: Session, filters: c.QueueFilter | None = None, page: int = 1, page_size: int = 50) -> c.QueuePage:
    filters = filters or c.QueueFilter()
    ref, total, rows = repo.query_queue(session, filters, page_size, (page - 1) * page_size)
    items = [
        c.QueueRow(
            visit_ref=r.visit_ref, patient_ref=r.patient_ref, arrival_at=r.arrival_at,
            registered_at=r.registered_at, department_code=r.department_code,
            triage_category=r.triage_category, status=r.status, waiting_minutes=round(r.waiting_minutes, 1),
            assigned_staff_ref=r.assigned_staff_ref, bed_ref=r.bed_ref,
            investigation_status=r.investigation_status, discharged_at=r.discharged_at,
        )
        for r in rows
    ]
    return c.QueuePage(items=items, total=total, page=page, page_size=page_size, as_of=repo.reference_time(session))


def get_visit_counts(session: Session) -> c.VisitCounts:
    as_of, row = repo.visit_counts(session)
    return c.VisitCounts(
        as_of=as_of, total_visits=row[0], waiting=row[1], in_treatment=row[2], discharged=row[3],
        critical_active=row[4],
    )


def get_waiting_metrics(
    session: Session, department_code: str | None = None, window_minutes: int | None = None
) -> c.WaitingMetrics:
    ref, waits = repo.waiting_minutes_list(session, department_code, window_minutes)
    buckets = [
        c.WaitBucket(
            label=label, min_minutes=lo, max_minutes=hi,
            count=sum(1 for w in waits if w >= lo and (hi is None or w < hi)),
        )
        for label, lo, hi in WAIT_BUCKETS
    ]
    return c.WaitingMetrics(
        as_of=repo.reference_time(session),
        waiting_patients=len(waits),
        avg_wait_minutes=round(sum(waits) / len(waits), 2) if waits else 0.0,
        max_wait_minutes=round(max(waits), 2) if waits else 0.0,
        distribution=buckets,
    )


def get_pending_investigations(
    session: Session, department_code: str | None = None, limit: int = 50
) -> c.PendingInvestigations:
    ref, rows = repo.pending_investigations(session, department_code)
    items = []
    for r in rows:
        age = (ref - r.requested_at).total_seconds() / 60.0
        items.append(
            c.PendingInvestigationItem(
                visit_ref=r.visit_ref, patient_ref=r.patient_ref, department_code=r.department_code,
                facility_code=r.facility_code, requested_at=r.requested_at, age_minutes=round(age, 1),
                expected_minutes=r.expected_minutes, delay_minutes=round(max(0.0, age - r.expected_minutes), 1),
            )
        )
    ages = [i.age_minutes for i in items]
    per_facility: dict[str, list[float]] = {}
    for i in items:
        per_facility.setdefault(i.facility_code, []).append(i.age_minutes)
    items.sort(key=lambda i: i.age_minutes, reverse=True)
    return c.PendingInvestigations(
        as_of=repo.reference_time(session),
        pending_count=len(items),
        avg_age_minutes=round(sum(ages) / len(ages), 2) if ages else 0.0,
        max_age_minutes=max(ages) if ages else 0.0,
        avg_delay_minutes=round(sum(i.delay_minutes for i in items) / len(items), 2) if items else 0.0,
        by_facility=[
            c.FacilityPending(facility_code=k, pending=len(v), avg_age_minutes=round(sum(v) / len(v), 2))
            for k, v in sorted(per_facility.items())
        ],
        items=items[:limit],
    )


def get_arrivals_over_time(
    session: Session, bucket_minutes: int = 30, window_minutes: int = 240
) -> list[c.ArrivalPoint]:
    ref = repo.effective_reference(session)
    start = ref - timedelta(minutes=window_minutes)
    arrivals = repo.arrival_times(session, start)
    n = max(1, window_minutes // bucket_minutes)
    points = []
    for i in range(n):
        lo = start + timedelta(minutes=i * bucket_minutes)
        hi = lo + timedelta(minutes=bucket_minutes)
        points.append(c.ArrivalPoint(bucket_start=lo, count=sum(1 for a in arrivals if lo <= a < hi)))
    return points


def get_department_workload(session: Session) -> list[c.DepartmentWorkload]:
    return [
        c.DepartmentWorkload(
            department_code=r.department_code, waiting=r.waiting, in_treatment=r.in_treatment,
            pending_investigations=r.pending, total_active=r.waiting + r.in_treatment,
        )
        for r in repo.workload_by_department(session)
    ]
