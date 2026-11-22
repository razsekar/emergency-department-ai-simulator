"""Typed contracts of the patient_queue module."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

VisitStatus = Literal["waiting", "in_treatment", "discharged"]
TriageCategory = Literal["critical", "urgent", "semi_urgent", "non_urgent"]
InvestigationStatus = Literal["none", "pending", "completed"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


# ---- dataset specs (written by the simulation module) ----
class VisitSpec(_Frozen):
    visit_ref: str
    patient_ref: str
    arrival_at: datetime
    registered_at: datetime | None = None
    department_code: str
    triage_category: TriageCategory
    status: VisitStatus
    treatment_started_at: datetime | None = None
    assigned_staff_ref: str | None = None
    bed_ref: str | None = None
    discharged_at: datetime | None = None


class InvestigationSpec(_Frozen):
    visit_ref: str
    facility_code: str
    investigation_type: str
    status: Literal["pending", "completed"]
    requested_at: datetime
    completed_at: datetime | None = None
    expected_minutes: int


class DatasetSpec(_Frozen):
    reference_time: datetime
    visits: list[VisitSpec]
    investigations: list[InvestigationSpec]


# ---- read models ----
class QueueFilter(BaseModel):
    status: VisitStatus | None = None
    department_code: str | None = None
    triage_category: TriageCategory | None = None
    investigation_status: InvestigationStatus | None = None
    min_wait_minutes: float | None = None
    max_wait_minutes: float | None = None
    arrived_within_minutes: int | None = None


class QueueRow(BaseModel):
    visit_ref: str
    patient_ref: str
    arrival_at: datetime
    registered_at: datetime | None
    department_code: str
    triage_category: TriageCategory
    status: VisitStatus
    waiting_minutes: float
    assigned_staff_ref: str | None
    bed_ref: str | None
    investigation_status: InvestigationStatus
    discharged_at: datetime | None


class QueuePage(BaseModel):
    items: list[QueueRow]
    total: int
    page: int
    page_size: int
    as_of: datetime | None


class VisitCounts(BaseModel):
    as_of: datetime | None
    total_visits: int
    waiting: int
    in_treatment: int
    discharged: int
    critical_active: int


class WaitBucket(BaseModel):
    label: str
    min_minutes: float
    max_minutes: float | None
    count: int


class WaitingMetrics(BaseModel):
    as_of: datetime | None
    waiting_patients: int
    avg_wait_minutes: float
    max_wait_minutes: float
    distribution: list[WaitBucket]


class PendingInvestigationItem(BaseModel):
    visit_ref: str
    patient_ref: str
    department_code: str
    facility_code: str
    requested_at: datetime
    age_minutes: float
    expected_minutes: int
    delay_minutes: float


class FacilityPending(BaseModel):
    facility_code: str
    pending: int
    avg_age_minutes: float


class PendingInvestigations(BaseModel):
    as_of: datetime | None
    pending_count: int
    avg_age_minutes: float
    max_age_minutes: float
    avg_delay_minutes: float
    by_facility: list[FacilityPending]
    items: list[PendingInvestigationItem]


class ArrivalPoint(BaseModel):
    bucket_start: datetime
    count: int


class DepartmentWorkload(BaseModel):
    department_code: str
    waiting: int
    in_treatment: int
    pending_investigations: int
    total_active: int
