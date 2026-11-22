"""Typed contracts for the model comparison feature (also used by the API layer)."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.modules.ai_orchestration.application.contracts import (
    ProviderName,
    RetrievedPolicyView,
    ToolExecutionView,
)
from app.modules.ai_orchestration.domain.comparison_scoring import SCORING_NOTE
from app.modules.ai_orchestration.domain.prompts import FIXED_DEMO_QUESTION
from app.modules.model_providers.public import Usage

DEMO_LABEL = "Demonstration comparison, not a formal benchmark."
MIN_MODELS = 2
MAX_MODELS = 6


class ModelSelection(BaseModel):
    provider: ProviderName
    model: str = Field(min_length=1, max_length=255)
    temperature: float | None = Field(default=None, ge=0, le=2)


class ComparisonRunRequest(BaseModel):
    question: str = Field(default=FIXED_DEMO_QUESTION, min_length=3, max_length=2000)
    selections: list[ModelSelection] = Field(min_length=MIN_MODELS, max_length=MAX_MODELS)

    @model_validator(mode="after")
    def _unique(self) -> "ComparisonRunRequest":
        pairs = [(s.provider, s.model) for s in self.selections]
        if len(set(pairs)) != len(pairs):
            raise ValueError("Each provider/model pair may be selected only once")
        return self


class SharedContextView(BaseModel):
    """The ONE frozen input every model answered from."""

    scenario_key: str | None
    scenario_name: str | None
    data_version: int | None
    snapshot_metrics: dict[str, Any]
    tools_executed: list[ToolExecutionView]
    retrieved_policies: list[RetrievedPolicyView]
    context_sha256: str = Field(description="SHA-256 of the exact system+user prompt every model received")


class ModelResultView(BaseModel):
    position: int
    provider: str
    model: str
    temperature: float | None
    status: Literal["completed", "failed", "not_configured"]
    error: str | None = None
    answer: str | None = None
    latency_ms: int | None = None
    usage: Usage = Usage()
    estimated_cost_usd: float | None = None  # None = unknown, never guessed
    tool_calling_supported: bool | None = None
    data_disclosure: str | None = None
    context_sha256: str | None = Field(default=None, description="Hash of the prompt this model actually received")
    scores: dict[str, Any] = {}
    citation_check: dict[str, Any] = {}


class ComparisonRunResponse(BaseModel):
    id: UUID
    label: str = DEMO_LABEL
    scoring_note: str = SCORING_NOTE
    question: str
    status: Literal["completed", "partial", "failed"]
    data_version_consistent: bool
    identical_context_verified: bool = Field(
        description="True when every model's received prompt hash equals the shared context hash"
    )
    shared_context: SharedContextView
    results: list[ModelResultView]
    created_by: str
    created_at: datetime


class ComparisonSummary(BaseModel):
    id: UUID
    label: str = DEMO_LABEL
    question: str
    status: str
    scenario_name: str | None
    data_version: int | None
    data_version_consistent: bool
    models: list[str]
    created_at: datetime


class ComparisonPage(BaseModel):
    items: list[ComparisonSummary]
    total: int
    limit: int
    offset: int
