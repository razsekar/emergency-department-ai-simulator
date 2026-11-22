"""HTTP layer for model comparison: validation, RBAC and serialisation only."""
import uuid

from fastapi import APIRouter, Depends, Query

from app.modules.ai_orchestration.application import comparison_contracts as cc
from app.modules.ai_orchestration.application import comparison_service as service
from app.modules.ai_orchestration.application.comparison_service import ComparisonService
from app.modules.ai_orchestration.application.comparison_wiring import get_comparison_service
from app.modules.identity.public import CurrentUser, Permission, require_permission

router = APIRouter(tags=["model-comparison"])

comparison_user = require_permission(Permission.COMPARISON_RUN)


@router.post("/api/comparison/run", response_model=cc.ComparisonRunResponse)
def run_comparison(body: cc.ComparisonRunRequest, user: CurrentUser = Depends(comparison_user),
                   svc: ComparisonService = Depends(get_comparison_service)) -> cc.ComparisonRunResponse:
    """Demonstration comparison (not a benchmark): every model answers from the same frozen data and context."""
    return svc.run(question=body.question, selections=body.selections, actor=user.username)


@router.get("/api/comparison/runs", response_model=cc.ComparisonPage, dependencies=[Depends(comparison_user)])
def list_comparison_runs(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                         data_version: int | None = Query(None, ge=0)) -> cc.ComparisonPage:
    return service.list_comparisons(limit, offset, data_version)


@router.get("/api/comparison/runs/{comparison_id}", response_model=cc.ComparisonRunResponse,
            dependencies=[Depends(comparison_user)])
def get_comparison_run(comparison_id: uuid.UUID) -> cc.ComparisonRunResponse:
    return service.get_comparison(comparison_id)
