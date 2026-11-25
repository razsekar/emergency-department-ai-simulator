"""Public interface of the analytics module. Other modules may import ONLY this file.

Contracts (take an open SQLAlchemy ``session``; computed fresh from records on every call):

  get_dashboard_metrics(session, bucket_minutes=30, window_minutes=240) -> DashboardMetrics
  get_resource_utilization(session)                                     -> ResourceUtilization

DashboardMetrics carries ``data_version`` and scenario identity so any consumer (agent tools,
analysis history) can trace results to the exact data state. No result is cached.
"""
from app.modules.analytics.application.contracts import (
    BedSummary,
    DashboardMetrics,
    FacilityLoad,
    ResourceUtilization,
    StaffSummary,
)
from app.modules.analytics.application.service import get_dashboard_metrics, get_resource_utilization
from app.modules.analytics.domain.escalation import EscalationAssessment, IndicatorResult, assess_escalation

# assess_escalation(metrics: Mapping) -> EscalationAssessment
#   Deterministic GREEN/AMBER/RED operating level from a metrics dict (the keys the dashboard/snapshot use:
#   patients_waiting, avg_wait_minutes, beds_available, doctors_on_duty, nurses_on_duty, pending_investigations).
#   Bands mirror the fictional demo escalation policy; see domain/escalation.py for the exact rule and limits.

__all__ = [
    "BedSummary", "DashboardMetrics", "EscalationAssessment", "FacilityLoad", "IndicatorResult",
    "ResourceUtilization", "StaffSummary", "assess_escalation", "get_dashboard_metrics", "get_resource_utilization",
]
