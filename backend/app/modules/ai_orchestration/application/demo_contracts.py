"""Typed contracts of the demonstration mode (same question, different data)."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.ai_orchestration.application.contracts import AgentMode, ProviderName
from app.modules.model_providers.public import Usage

DemoScenario = Literal["normal", "surge", "recovery"]


class DemoStepRequest(BaseModel):
    """The question is fixed by the backend; the presenter chooses the scenario and the model."""

    scenario: DemoScenario
    provider: ProviderName
    model: str = Field(min_length=1, max_length=255)
    temperature: float | None = Field(default=None, ge=0, le=2)
    mode: AgentMode = "auto"


class MetricChange(BaseModel):
    metric: str
    before: Any = None
    after: Any = None


class StepVerification(BaseModel):
    """Evidence that the underlying records changed before the question was asked."""

    data_version_before: int
    data_version_after: int
    data_version_changed: bool
    compared_to: Literal["previous_run", "state_before_step"]
    metrics_changed: bool
    changed_metrics: list[MetricChange]
    question_identical: bool
    analysis_data_version_matches: bool = Field(
        description="The agent run analysed exactly the data version this step produced"
    )
    note: str | None = None


class DemoRunView(BaseModel):
    id: UUID
    session_id: UUID
    run_number: int
    run_label: str
    analysis_run_id: UUID | None
    scenario_key: str | None
    scenario_name: str | None
    data_version: int
    patient_record_count: int
    metrics: dict[str, Any]
    verification: StepVerification | None
    tools_executed: list[dict[str, Any]]
    retrieved_policies: list[dict[str, Any]]
    question: str
    question_sha256: str
    final_answer: str | None
    provider: str
    model: str
    latency_ms: int
    usage: Usage
    estimated_cost_usd: float | None
    created_by: str
    created_at: datetime


class MetricComparisonRow(BaseModel):
    metric: str
    values: list[Any]
    differs: bool
    deltas_vs_previous: list[float | None]


class DemoSessionView(BaseModel):
    session_id: UUID | None
    question: str
    question_sha256: str
    run_count: int
    runs: list[DemoRunView]
    metric_comparison: list[MetricComparisonRow]


class DemoStepResponse(BaseModel):
    run: DemoRunView
    run_count: int
    metric_comparison: list[MetricComparisonRow]


class DemoResetResponse(BaseModel):
    cleared_runs: int
    baseline_scenario: str
    data_version: int
