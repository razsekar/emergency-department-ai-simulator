"""Analytics use cases: compose read-only data from the owning modules' public interfaces.

Nothing is cached or stored, so every call reflects the current data_version.
"""
from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy.orm import Session

from app.modules.analytics.application import contracts as c
from app.modules.patient_queue import public as queue
from app.modules.resource_management import public as resources
from app.modules.simulation import public as simulation
from app.platform.db import unit_of_work

T = TypeVar("T")


def run(fn: Callable[..., T], /, **kwargs: Any) -> T:
    with unit_of_work() as session:
        return fn(session, **kwargs)


def _pct(part: float, whole: float) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def get_resource_utilization(session: Session) -> c.ResourceUtilization:
    state = simulation.get_data_state(session)
    beds = resources.get_bed_availability(session)
    staff = resources.get_staff_availability(session)
    pending = queue.get_pending_investigations(session, limit=1)
    pending_by_fac = {f.facility_code: f for f in pending.by_facility}
    facilities = []
    for f in resources.list_facilities(session):
        p = pending_by_fac.get(f.code)
        count = p.pending if p else 0
        facilities.append(
            c.FacilityLoad(
                code=f.code, name=f.name, capacity=f.capacity, pending_requests=count,
                load_ratio=round(count / f.capacity, 2) if f.capacity else 0.0,
                avg_age_minutes=p.avg_age_minutes if p else 0.0,
            )
        )
    by_role = {t.role: t for t in staff.totals_by_role}
    return c.ResourceUtilization(
        data_version=state.data_version,
        beds_pct=beds.utilization_pct,
        doctors_pct=by_role["doctor"].utilization_pct if "doctor" in by_role else 0.0,
        nurses_pct=by_role["nurse"].utilization_pct if "nurse" in by_role else 0.0,
        facilities=facilities,
        departments=[d.model_dump() for d in resources.get_department_capacity(session)],
    )


def get_dashboard_metrics(session: Session, bucket_minutes: int = 30, window_minutes: int = 240) -> c.DashboardMetrics:
    state = simulation.get_data_state(session)
    counts = queue.get_visit_counts(session)
    waiting = queue.get_waiting_metrics(session)
    pending = queue.get_pending_investigations(session, limit=1)
    beds = resources.get_bed_availability(session)
    staff = resources.get_staff_availability(session)
    return c.DashboardMetrics(
        data_version=state.data_version,
        scenario_key=state.scenario_key,
        scenario_name=state.scenario_name,
        as_of=counts.as_of,
        total_visits=counts.total_visits,
        patients_waiting=counts.waiting,
        patients_in_treatment=counts.in_treatment,
        completed_discharges=counts.discharged,
        critical_patients=counts.critical_active,
        beds=c.BedSummary(
            total=beds.total_beds, occupied=beds.occupied_beds, available=beds.available_beds,
            utilization_pct=beds.utilization_pct,
        ),
        staff=[
            c.StaffSummary(role=t.role, on_duty=t.on_duty, available=t.available, busy=t.busy,
                           utilization_pct=t.utilization_pct)
            for t in staff.totals_by_role
        ],
        avg_wait_minutes=waiting.avg_wait_minutes,
        max_wait_minutes=waiting.max_wait_minutes,
        pending_investigations=pending.pending_count,
        avg_pending_investigation_age_minutes=pending.avg_age_minutes,
        avg_pending_investigation_delay_minutes=pending.avg_delay_minutes,
        department_workload=queue.get_department_workload(session),
        arrivals_over_time=queue.get_arrivals_over_time(session, bucket_minutes, window_minutes),
        waiting_time_distribution=waiting.distribution,
        resource_utilization=get_resource_utilization(session),
    )
