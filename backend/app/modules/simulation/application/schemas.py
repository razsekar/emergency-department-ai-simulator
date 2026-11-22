"""Typed request/response contracts of the simulation module."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.simulation.domain.params import ScenarioOverrides, ScenarioParams

__all__ = [
    "ApplyRequest", "ApplyResponse", "DataState", "RunPage", "ScenarioInfo", "ScenarioOverrides",
    "ScenarioParams", "ScenarioRunInfo",
]


class ApplyRequest(BaseModel):
    scenario_key: Literal["normal", "surge", "recovery", "custom"] = Field(
        description="Base scenario. 'custom' starts from the Normal parameters."
    )
    overrides: ScenarioOverrides | None = Field(
        default=None, description="Manual parameter edits; any override turns the run into a Custom Scenario."
    )


class DataState(BaseModel):
    data_version: int
    scenario_key: str | None
    scenario_name: str | None
    applied_at: datetime | None
    last_run_id: UUID | None


class ScenarioInfo(BaseModel):
    key: str
    name: str
    description: str
    is_builtin: bool
    is_current: bool
    parameters: ScenarioParams


class ScenarioRunInfo(BaseModel):
    id: UUID
    scenario_key: str
    scenario_name: str
    trigger: str
    status: str
    data_version: int | None
    parameters: dict
    validation: list[dict] | None
    error: str | None
    record_count: int
    duration_ms: int
    created_at: datetime


class ApplyResponse(BaseModel):
    state: DataState
    run: ScenarioRunInfo


class RunPage(BaseModel):
    items: list[ScenarioRunInfo]
    total: int
    limit: int
    offset: int
