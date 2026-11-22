"""HTTP endpoints for the patient queue. Controllers delegate to application use cases."""
from typing import Annotated

from fastapi import APIRouter, Query

from app.modules.patient_queue.application import contracts as c
from app.modules.patient_queue.application import service

router = APIRouter(prefix="/api/patient-queue", tags=["patient-queue"])

Department = Annotated[str | None, Query(description="Department code, e.g. ACUTE")]


@router.get("", response_model=c.QueuePage)
def queue(
    status: Annotated[c.VisitStatus | None, Query()] = None,
    department: Department = None,
    triage_category: Annotated[c.TriageCategory | None, Query(description="Simulated triage category")] = None,
    investigation_status: Annotated[c.InvestigationStatus | None, Query()] = None,
    min_wait_minutes: Annotated[float | None, Query(ge=0)] = None,
    max_wait_minutes: Annotated[float | None, Query(ge=0)] = None,
    arrived_within_minutes: Annotated[int | None, Query(ge=1, le=1440)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> c.QueuePage:
    filters = c.QueueFilter(
        status=status, department_code=department, triage_category=triage_category,
        investigation_status=investigation_status, min_wait_minutes=min_wait_minutes,
        max_wait_minutes=max_wait_minutes, arrived_within_minutes=arrived_within_minutes,
    )
    return service.run(service.get_queue, filters=filters, page=page, page_size=page_size)


@router.get("/waiting-metrics", response_model=c.WaitingMetrics)
def waiting_metrics(
    department: Department = None,
    window_minutes: Annotated[int | None, Query(ge=1, le=1440)] = None,
) -> c.WaitingMetrics:
    return service.run(service.get_waiting_metrics, department_code=department, window_minutes=window_minutes)


@router.get("/pending-investigations", response_model=c.PendingInvestigations)
def pending_investigations(
    department: Department = None, limit: Annotated[int, Query(ge=1, le=500)] = 50
) -> c.PendingInvestigations:
    return service.run(service.get_pending_investigations, department_code=department, limit=limit)
