"""HTTP endpoints for scenario management. Controllers delegate to application use cases."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.modules.identity.public import CurrentUser, Permission, require_permission
from app.modules.simulation.application import schemas as s
from app.modules.simulation.application import service

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])
read = Depends(require_permission(Permission.SCENARIO_READ))


@router.get("", response_model=list[s.ScenarioInfo], dependencies=[read])
def list_scenarios() -> list[s.ScenarioInfo]:
    return service.list_scenarios()


@router.get("/current", response_model=s.DataState, dependencies=[read])
def current_state() -> s.DataState:
    return service.current_state()


@router.get("/history", response_model=s.RunPage, dependencies=[read])
def history(
    limit: Annotated[int, Query(ge=1, le=200)] = 50, offset: Annotated[int, Query(ge=0)] = 0
) -> s.RunPage:
    return service.get_history(limit=limit, offset=offset)


@router.post("/apply", response_model=s.ApplyResponse)
def apply(
    request: s.ApplyRequest, user: CurrentUser = Depends(require_permission(Permission.SCENARIO_APPLY))
) -> s.ApplyResponse:
    return service.apply_scenario(request.scenario_key, request.overrides, actor=user.username)


@router.post("/randomize", response_model=s.ApplyResponse)
def randomize(user: CurrentUser = Depends(require_permission(Permission.SCENARIO_APPLY))) -> s.ApplyResponse:
    return service.randomize_scenario(actor=user.username)


@router.post("/reset", response_model=s.ApplyResponse)
def reset(user: CurrentUser = Depends(require_permission(Permission.SCENARIO_RESET))) -> s.ApplyResponse:
    return service.reset_database(actor=user.username)
