"""Demonstration-mode HTTP layer: validation, RBAC and serialisation only."""
from fastapi import APIRouter, Depends

from app.modules.ai_orchestration.application import demo_contracts as d
from app.modules.ai_orchestration.application import service
from app.modules.ai_orchestration.application.demo_service import DemoService
from app.modules.ai_orchestration.application.demo_wiring import get_demo_service
from app.modules.identity.public import CurrentUser, Permission, require_permission

demo_router = APIRouter(prefix="/api/demo", tags=["demo"])

agent_user = require_permission(Permission.AGENT_RUN)
apply_user = require_permission(Permission.SCENARIO_APPLY)
reset_user = require_permission(Permission.SCENARIO_RESET)


@demo_router.get("/question")
def question(_: CurrentUser = Depends(agent_user)) -> dict[str, str]:
    return {"question": service.demo_question()}


@demo_router.post("/step", response_model=d.DemoStepResponse, dependencies=[Depends(apply_user)])
def step(body: d.DemoStepRequest, user: CurrentUser = Depends(agent_user),
         svc: DemoService = Depends(get_demo_service)) -> d.DemoStepResponse:
    return svc.step(body, actor=user.username)


@demo_router.get("/session", response_model=d.DemoSessionView, dependencies=[Depends(agent_user)])
def session(svc: DemoService = Depends(get_demo_service)) -> d.DemoSessionView:
    return svc.session()


@demo_router.post("/session/reset", response_model=d.DemoResetResponse)
def reset(user: CurrentUser = Depends(reset_user), svc: DemoService = Depends(get_demo_service)) -> d.DemoResetResponse:
    return svc.reset(actor=user.username)
