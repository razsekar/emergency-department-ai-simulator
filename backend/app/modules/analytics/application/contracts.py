"""Typed contracts of the analytics module (read models only; computed from live records)."""
from datetime import datetime

from pydantic import BaseModel

from app.modules.patient_queue.public import ArrivalPoint, DepartmentWorkload, WaitBucket
from app.modules.resource_management.public import RoleTotals


class BedSummary(BaseModel):
    total: int
    occupied: int
    available: int
    utilization_pct: float


class StaffSummary(BaseModel):
    role: str
    on_duty: int
    available: int
    busy: int
    utilization_pct: float


class FacilityLoad(BaseModel):
    code: str
    name: str
    capacity: int
    pending_requests: int
    load_ratio: float  # pending requests per unit of capacity
    avg_age_minutes: float


class ResourceUtilization(BaseModel):
    data_version: int
    beds_pct: float
    doctors_pct: float
    nurses_pct: float
    facilities: list[FacilityLoad]
    departments: list[dict]


class DashboardMetrics(BaseModel):
    """Everything on the operations dashboard, calculated from database records at request time."""

    data_version: int
    scenario_key: str | None
    scenario_name: str | None
    as_of: datetime | None
    total_visits: int
    patients_waiting: int
    patients_in_treatment: int
    completed_discharges: int
    critical_patients: int
    beds: BedSummary
    staff: list[StaffSummary]
    avg_wait_minutes: float
    max_wait_minutes: float
    pending_investigations: int
    avg_pending_investigation_age_minutes: float
    avg_pending_investigation_delay_minutes: float
    department_workload: list[DepartmentWorkload]
    arrivals_over_time: list[ArrivalPoint]
    waiting_time_distribution: list[WaitBucket]
    resource_utilization: ResourceUtilization


__all__ = [
    "ArrivalPoint", "BedSummary", "DashboardMetrics", "DepartmentWorkload", "FacilityLoad",
    "ResourceUtilization", "RoleTotals", "StaffSummary", "WaitBucket",
]
