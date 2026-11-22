"""Scenario parameter model (the control-panel inputs)."""
from pydantic import BaseModel, ConfigDict, Field, model_validator

DEPARTMENT_CODES = ("ACUTE", "RESUS", "MINOR", "PEDS")
DEFAULT_WORKLOAD = {"ACUTE": 0.40, "RESUS": 0.10, "MINOR": 0.30, "PEDS": 0.20}
# Generated waits are spread between 0.4x and ~1.65x of the mean; the analysis window must contain them.
WINDOW_FACTOR = 1.8


class ScenarioParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: int = Field(ge=0, le=2**31 - 1, description="Deterministic generation seed")
    arrival_rate_per_hour: float = Field(ge=0, le=200)
    beds_available: int = Field(ge=0, le=100)
    beds_occupied: int = Field(ge=0, le=100)
    doctors_on_duty: int = Field(ge=0, le=100)
    nurses_on_duty: int = Field(ge=0, le=200)
    waiting_patients: int = Field(ge=0, le=300, description="Pending patients in the queue")
    avg_wait_minutes: float = Field(ge=1, le=240, description="Target mean waiting time of waiting patients")
    pending_investigations: int = Field(ge=0, le=300)
    investigation_delay_minutes: float = Field(ge=1, le=240, description="Target mean age of pending requests")
    department_workload: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_WORKLOAD))
    window_minutes: int = Field(ge=60, le=1440, description="Time window for analysis")

    @model_validator(mode="after")
    def _cross_checks(self) -> "ScenarioParams":
        unknown = set(self.department_workload) - set(DEPARTMENT_CODES)
        if unknown:
            raise ValueError(f"unknown departments in department_workload: {sorted(unknown)}")
        if any(w < 0 for w in self.department_workload.values()) or sum(self.department_workload.values()) <= 0:
            raise ValueError("department_workload weights must be non-negative with a positive sum")
        if self.beds_available + self.beds_occupied < 1:
            raise ValueError("at least one bed is required")
        if self.pending_investigations > self.waiting_patients + self.beds_occupied:
            raise ValueError(
                "pending_investigations cannot exceed waiting_patients + beds_occupied (active patients)"
            )
        if self.window_minutes < WINDOW_FACTOR * self.avg_wait_minutes:
            raise ValueError(
                f"window_minutes must be at least {WINDOW_FACTOR} x avg_wait_minutes to hold the generated waits"
            )
        return self

    def normalized_workload(self) -> dict[str, float]:
        total = sum(self.department_workload.values())
        return {c: self.department_workload.get(c, 0.0) / total for c in DEPARTMENT_CODES}


class ScenarioOverrides(BaseModel):
    """Partial parameters for the manual editor; unset fields keep the base scenario's values."""

    model_config = ConfigDict(extra="forbid")

    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)
    arrival_rate_per_hour: float | None = Field(default=None, ge=0, le=200)
    beds_available: int | None = Field(default=None, ge=0, le=100)
    beds_occupied: int | None = Field(default=None, ge=0, le=100)
    doctors_on_duty: int | None = Field(default=None, ge=0, le=100)
    nurses_on_duty: int | None = Field(default=None, ge=0, le=200)
    waiting_patients: int | None = Field(default=None, ge=0, le=300)
    avg_wait_minutes: float | None = Field(default=None, ge=1, le=240)
    pending_investigations: int | None = Field(default=None, ge=0, le=300)
    investigation_delay_minutes: float | None = Field(default=None, ge=1, le=240)
    department_workload: dict[str, float] | None = None
    window_minutes: int | None = Field(default=None, ge=60, le=1440)
