"""The three built-in demonstration scenarios (illustrative synthetic configurations)."""
from dataclasses import dataclass

from app.modules.simulation.domain.params import DEFAULT_WORKLOAD, ScenarioParams


@dataclass(frozen=True)
class BuiltinScenario:
    key: str
    name: str
    description: str
    params: ScenarioParams


BUILTIN: dict[str, BuiltinScenario] = {
    "normal": BuiltinScenario(
        key="normal",
        name="Normal Operations",
        description="Steady arrivals, adequate beds and staffing, short queue.",
        params=ScenarioParams(
            seed=1001, arrival_rate_per_hour=8, beds_available=8, beds_occupied=10, doctors_on_duty=6,
            nurses_on_duty=10, waiting_patients=12, avg_wait_minutes=15, pending_investigations=5,
            investigation_delay_minutes=20, department_workload=dict(DEFAULT_WORKLOAD), window_minutes=240,
        ),
    ),
    "surge": BuiltinScenario(
        key="surge",
        name="Emergency Surge",
        description="High arrivals, one free bed, thin staffing, long queue and investigation backlog.",
        params=ScenarioParams(
            seed=2002, arrival_rate_per_hour=25, beds_available=1, beds_occupied=15, doctors_on_duty=3,
            nurses_on_duty=4, waiting_patients=38, avg_wait_minutes=75, pending_investigations=28,
            investigation_delay_minutes=60, department_workload=dict(DEFAULT_WORKLOAD), window_minutes=240,
        ),
    ),
    "recovery": BuiltinScenario(
        key="recovery",
        name="Recovery Operations",
        description="Arrivals normalised, beds freed, additional staff on duty, queue clearing.",
        params=ScenarioParams(
            seed=3003, arrival_rate_per_hour=8, beds_available=10, beds_occupied=6, doctors_on_duty=7,
            nurses_on_duty=12, waiting_patients=9, avg_wait_minutes=18, pending_investigations=4,
            investigation_delay_minutes=15, department_workload=dict(DEFAULT_WORKLOAD), window_minutes=240,
        ),
    ),
}

CUSTOM_KEY = "custom"
CUSTOM_NAME = "Custom Scenario"
CUSTOM_DESCRIPTION = "User-defined or randomized parameters."
