"""Fresh snapshot of the simulation at the moment of a request. Never cached."""
from dataclasses import dataclass
from typing import Any

from app.modules.analytics import public as analytics
from app.platform.db import unit_of_work


@dataclass(frozen=True)
class Snapshot:
    data_version: int
    scenario_key: str | None
    scenario_name: str | None
    metrics: dict[str, Any]


def take_snapshot() -> Snapshot:
    with unit_of_work() as session:
        m = analytics.get_dashboard_metrics(session)
    doctors = next((s for s in m.staff if s.role == "doctor"), None)
    nurses = next((s for s in m.staff if s.role == "nurse"), None)
    metrics = {
        "total_visits": m.total_visits,
        "patients_waiting": m.patients_waiting,
        "patients_in_treatment": m.patients_in_treatment,
        "completed_discharges": m.completed_discharges,
        "critical_patients": m.critical_patients,
        "beds_total": m.beds.total,
        "beds_occupied": m.beds.occupied,
        "beds_available": m.beds.available,
        "bed_utilization_pct": m.beds.utilization_pct,
        "doctors_on_duty": doctors.on_duty if doctors else 0,
        "doctors_available": doctors.available if doctors else 0,
        "nurses_on_duty": nurses.on_duty if nurses else 0,
        "nurses_available": nurses.available if nurses else 0,
        "avg_wait_minutes": m.avg_wait_minutes,
        "max_wait_minutes": m.max_wait_minutes,
        "pending_investigations": m.pending_investigations,
        "avg_pending_investigation_delay_minutes": m.avg_pending_investigation_delay_minutes,
    }
    return Snapshot(m.data_version, m.scenario_key, m.scenario_name, metrics)
