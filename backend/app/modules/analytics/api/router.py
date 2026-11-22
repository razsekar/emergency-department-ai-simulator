"""HTTP endpoints for the operations dashboard. Controllers delegate to application use cases."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.modules.analytics.application import contracts as c
from app.modules.analytics.application import service
from app.modules.identity.public import Permission, require_permission

router = APIRouter(
    prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(require_permission(Permission.DASHBOARD_READ))]
)


@router.get("/metrics", response_model=c.DashboardMetrics)
def metrics(
    bucket_minutes: Annotated[int, Query(ge=5, le=120)] = 30,
    window_minutes: Annotated[int, Query(ge=30, le=1440)] = 240,
) -> c.DashboardMetrics:
    return service.run(service.get_dashboard_metrics, bucket_minutes=bucket_minutes, window_minutes=window_minutes)


@router.get("/resource-utilization", response_model=c.ResourceUtilization)
def resource_utilization() -> c.ResourceUtilization:
    return service.run(service.get_resource_utilization)
