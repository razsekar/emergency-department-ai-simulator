"""Post-generation validation: persisted data must genuinely produce the requested scenario."""
from dataclasses import dataclass

from app.modules.simulation.domain.errors import ScenarioValidationError
from app.modules.simulation.domain.params import ScenarioParams

WAIT_TOLERANCE = 0.10  # relative
INVESTIGATION_AGE_TOLERANCE = 0.15


@dataclass(frozen=True)
class ObservedState:
    """What the owning modules report after the dataset was written."""

    beds_available: int
    beds_occupied: int
    doctors_on_duty: int
    nurses_on_duty: int
    waiting_patients: int
    avg_wait_minutes: float
    pending_investigations: int
    avg_pending_age_minutes: float
    total_visits: int


def validate_observed(params: ScenarioParams, observed: ObservedState) -> list[dict]:
    checks: list[dict] = []

    def exact(name: str, expected: int, actual: int) -> None:
        checks.append({"check": name, "expected": expected, "actual": actual, "ok": expected == actual})

    def approx(name: str, expected: float, actual: float, tol: float) -> None:
        ok = abs(actual - expected) <= max(tol * expected, 0.5)
        checks.append({"check": name, "expected": expected, "actual": round(actual, 2), "ok": ok})

    exact("beds_available", params.beds_available, observed.beds_available)
    exact("beds_occupied", params.beds_occupied, observed.beds_occupied)
    exact("doctors_on_duty", params.doctors_on_duty, observed.doctors_on_duty)
    exact("nurses_on_duty", params.nurses_on_duty, observed.nurses_on_duty)
    exact("waiting_patients", params.waiting_patients, observed.waiting_patients)
    exact("pending_investigations", params.pending_investigations, observed.pending_investigations)
    if params.waiting_patients:
        approx("avg_wait_minutes", params.avg_wait_minutes, observed.avg_wait_minutes, WAIT_TOLERANCE)
    if params.pending_investigations:
        approx(
            "avg_pending_age_minutes", params.investigation_delay_minutes, observed.avg_pending_age_minutes,
            INVESTIGATION_AGE_TOLERANCE,
        )
    failed = [c for c in checks if not c["ok"]]
    if failed:
        detail = "; ".join(f"{c['check']}: expected {c['expected']}, got {c['actual']}" for c in failed)
        raise ScenarioValidationError(f"Generated data does not match the scenario ({detail})")
    return checks
