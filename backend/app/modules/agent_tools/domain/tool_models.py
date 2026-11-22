"""Strict input and output models for the seven approved tools.

Inputs forbid unknown fields and constrain every value, so a model (or a prompt injection) cannot smuggle
free-form SQL, shell text or unexpected parameters through a tool call. Outputs are validated again after the
handler runs, so a malformed result never reaches the LLM.
"""
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

MAX_TOOL_INTERACTIONS = 5

DepartmentCode = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_\-]+$")
]
PolicyQuery = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]

PolicyTopic = Literal[
    "waiting_time", "bed_capacity", "staffing", "pending_investigations", "escalation", "discharge", "registration"
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------ inputs
class GetPatientQueueInput(_Strict):
    department: DepartmentCode | None = Field(default=None, description="Department code, e.g. ACUTE")
    status: Literal["waiting", "in_treatment", "discharged"] | None = Field(default=None, description="Visit status")
    window_minutes: int | None = Field(default=None, ge=1, le=1440, description="Only visits that arrived within this many minutes")
    limit: int = Field(default=20, ge=1, le=50, description="Maximum rows returned")


class GetBedAvailabilityInput(_Strict):
    department: DepartmentCode | None = Field(default=None, description="Department code; omit for all departments")


class GetStaffAvailabilityInput(_Strict):
    department: DepartmentCode | None = Field(default=None, description="Department code; omit for all departments")
    role: Literal["doctor", "nurse"] | None = Field(default=None, description="Staff role")


class CalculateWaitingMetricsInput(_Strict):
    department: DepartmentCode | None = Field(default=None, description="Department code; omit for all departments")
    window_minutes: int | None = Field(default=None, ge=1, le=1440, description="Only patients who arrived within this many minutes")


class GetPendingInvestigationsInput(_Strict):
    department: DepartmentCode | None = Field(default=None, description="Department code; omit for all departments")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum investigation rows returned")


class RetrieveHospitalProtocolInput(_Strict):
    topics: list[PolicyTopic] = Field(
        default_factory=list, max_length=7,
        description="Policy topics. Each topic is turned into a targeted search that includes the CURRENT metrics.",
    )
    queries: list[PolicyQuery] = Field(default_factory=list, max_length=5, description="Optional free-text policy searches")
    k: int = Field(default=3, ge=1, le=5, description="Results per search")

    @field_validator("topics", "queries")
    @classmethod
    def _unique(cls, v: list) -> list:
        return list(dict.fromkeys(v))

    def model_post_init(self, __context: Any) -> None:
        if not self.topics and not self.queries:
            raise ValueError("Provide at least one topic or query")


class GenerateDepartmentReportInput(_Strict):
    department: DepartmentCode | None = Field(default=None, description="Department code; omit for the whole ED")
    window_minutes: int | None = Field(default=None, ge=1, le=1440, description="Analysis time window in minutes")


# ------------------------------------------------------------------ outputs
class QueueItemOut(_Out):
    visit_ref: str
    patient_ref: str
    department_code: str
    triage_category: str
    status: str
    waiting_minutes: float
    investigation_status: str


class PatientQueueOutput(_Out):
    data_version: int
    as_of: datetime | None
    total_matching: int
    returned: int
    filters: dict[str, Any]
    items: list[QueueItemOut]


class DepartmentBedsOut(_Out):
    department_code: str
    department_name: str
    total_beds: int
    occupied_beds: int
    available_beds: int
    utilization_pct: float


class BedAvailabilityOutput(_Out):
    data_version: int
    total_beds: int
    occupied_beds: int
    available_beds: int
    utilization_pct: float
    by_department: list[DepartmentBedsOut]


class RoleTotalsOut(_Out):
    role: str
    on_duty: int
    available: int
    busy: int
    utilization_pct: float


class StaffGroupOut(_Out):
    department_code: str
    role: str
    on_duty: int
    available: int
    busy: int


class StaffAvailabilityOutput(_Out):
    data_version: int
    on_duty: int
    available: int
    busy: int
    totals_by_role: list[RoleTotalsOut]
    groups: list[StaffGroupOut]


class WaitBucketOut(_Out):
    label: str
    count: int


class WaitingMetricsOutput(_Out):
    data_version: int
    as_of: datetime | None
    filters: dict[str, Any]
    waiting_patients: int
    avg_wait_minutes: float
    max_wait_minutes: float
    distribution: list[WaitBucketOut]


class PendingItemOut(_Out):
    visit_ref: str
    department_code: str
    facility_code: str
    age_minutes: float
    expected_minutes: int
    delay_minutes: float


class FacilityPendingOut(_Out):
    facility_code: str
    pending: int
    avg_age_minutes: float


class PendingInvestigationsOutput(_Out):
    data_version: int
    as_of: datetime | None
    filters: dict[str, Any]
    pending_count: int
    avg_age_minutes: float
    max_age_minutes: float
    avg_delay_minutes: float
    by_facility: list[FacilityPendingOut]
    items: list[PendingItemOut]


class PolicyChunkOut(_Out):
    document_name: str
    page: int
    score: float
    matched_query: str
    excerpt: str
    flagged: bool = False  # True when prompt-injection heuristics fired; such text is withheld from the LLM


class ProtocolOutput(_Out):
    data_version: int
    queries_used: list[str]
    metrics_used: dict[str, Any]
    chunks: list[PolicyChunkOut]
    withheld_count: int
    context: str  # delimited, labelled UNTRUSTED-DATA block; flagged chunks excluded


class ReportSection(_Out):
    title: str
    metrics: dict[str, Any]
    observations: list[str]


class DepartmentReportOutput(_Out):
    data_version: int
    scenario_name: str | None
    as_of: datetime | None
    scope: dict[str, Any]
    sections: list[ReportSection]
    note: str
