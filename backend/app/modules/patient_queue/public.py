"""Public interface of the patient_queue module. Other modules may import ONLY this file.

Contracts (typed; all take an open SQLAlchemy ``session`` so callers control the transaction):

  replace_dataset(session, DatasetSpec)                  -> None   (used by the simulation module)
  get_reference_time(session)                            -> datetime | None  (the dataset clock)
  get_queue(session, QueueFilter, page, page_size)       -> QueuePage
  get_visit_counts(session)                              -> VisitCounts
  get_waiting_metrics(session, department_code, window_minutes) -> WaitingMetrics
  get_pending_investigations(session, department_code, limit)  -> PendingInvestigations
  get_arrivals_over_time(session, bucket_minutes, window_minutes) -> list[ArrivalPoint]
  get_department_workload(session)                       -> list[DepartmentWorkload]

Waiting durations are measured against the dataset clock (reference time frozen when a scenario
is applied), not the wall clock, so metrics do not drift during a demonstration.
Patient references are synthetic (SIM-PAT-001 ...). This module owns schema ``patient_queue``.
"""
from app.modules.patient_queue.application.contracts import (
    ArrivalPoint,
    DatasetSpec,
    DepartmentWorkload,
    FacilityPending,
    InvestigationSpec,
    PendingInvestigationItem,
    PendingInvestigations,
    QueueFilter,
    QueuePage,
    QueueRow,
    VisitCounts,
    VisitSpec,
    WaitBucket,
    WaitingMetrics,
)
from app.modules.patient_queue.application.service import (
    get_arrivals_over_time,
    get_department_workload,
    get_pending_investigations,
    get_queue,
    get_reference_time,
    get_visit_counts,
    get_waiting_metrics,
    replace_dataset,
)

__all__ = [
    "ArrivalPoint", "DatasetSpec", "DepartmentWorkload", "FacilityPending", "InvestigationSpec",
    "PendingInvestigationItem", "PendingInvestigations", "QueueFilter", "QueuePage", "QueueRow",
    "VisitCounts", "VisitSpec", "WaitBucket", "WaitingMetrics", "get_arrivals_over_time",
    "get_department_workload", "get_pending_investigations", "get_queue", "get_reference_time",
    "get_visit_counts", "get_waiting_metrics", "replace_dataset",
]
