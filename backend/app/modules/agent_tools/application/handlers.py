"""Tool handlers. Each reads fresh data through ANOTHER MODULE'S PUBLIC INTERFACE only.

No SQL, no shell, no tables of other modules: the LLM can only reach what these functions expose.
Every handler opens its own short transaction and reports the simulation `data_version` it observed.
"""
import hashlib
from typing import Any

from app.modules.agent_tools.domain import tool_models as m
from app.modules.agent_tools.domain.errors import ToolInputError
from app.modules.analytics import public as analytics
from app.modules.patient_queue import public as queue
from app.modules.rag import public as rag
from app.modules.resource_management import public as resources
from app.modules.simulation import public as simulation
from app.platform.db import unit_of_work

EXCERPT_CHARS = 700
MAX_POLICY_CHUNKS = 12
WITHHELD_TEXT = "[withheld: possible prompt injection in source text]"


def _version(session) -> int:
    return simulation.get_data_state(session).data_version


def _check_department(session, code: str | None) -> None:
    if code is None:
        return
    valid = [d.department_code for d in resources.get_department_capacity(session)]
    if code not in valid:
        raise ToolInputError(f"Unknown department '{code}'. Valid departments: {', '.join(sorted(valid)) or 'none loaded'}")


def get_patient_queue(args: m.GetPatientQueueInput) -> dict[str, Any]:
    with unit_of_work() as session:
        _check_department(session, args.department)
        page = queue.get_queue(
            session,
            queue.QueueFilter(status=args.status, department_code=args.department, arrived_within_minutes=args.window_minutes),
            page=1,
            page_size=args.limit,
        )
        return {
            "data_version": _version(session),
            "as_of": page.as_of,
            "total_matching": page.total,
            "returned": len(page.items),
            "filters": {"department": args.department, "status": args.status, "window_minutes": args.window_minutes},
            "items": [
                {
                    "visit_ref": r.visit_ref, "patient_ref": r.patient_ref, "department_code": r.department_code,
                    "triage_category": r.triage_category, "status": r.status, "waiting_minutes": r.waiting_minutes,
                    "investigation_status": r.investigation_status,
                }
                for r in page.items
            ],
        }


def get_bed_availability(args: m.GetBedAvailabilityInput) -> dict[str, Any]:
    with unit_of_work() as session:
        _check_department(session, args.department)
        b = resources.get_bed_availability(session, args.department)
        return {
            "data_version": _version(session),
            "total_beds": b.total_beds, "occupied_beds": b.occupied_beds, "available_beds": b.available_beds,
            "utilization_pct": b.utilization_pct,
            "by_department": [d.model_dump() for d in b.by_department],
        }


def get_staff_availability(args: m.GetStaffAvailabilityInput) -> dict[str, Any]:
    with unit_of_work() as session:
        _check_department(session, args.department)
        s = resources.get_staff_availability(session, args.department, args.role)
        return {
            "data_version": _version(session),
            "on_duty": s.on_duty, "available": s.available, "busy": s.busy,
            "totals_by_role": [t.model_dump() for t in s.totals_by_role],
            "groups": [g.model_dump() for g in s.groups],
        }


def calculate_waiting_metrics(args: m.CalculateWaitingMetricsInput) -> dict[str, Any]:
    with unit_of_work() as session:
        _check_department(session, args.department)
        w = queue.get_waiting_metrics(session, args.department, args.window_minutes)
        return {
            "data_version": _version(session), "as_of": w.as_of,
            "filters": {"department": args.department, "window_minutes": args.window_minutes},
            "waiting_patients": w.waiting_patients, "avg_wait_minutes": w.avg_wait_minutes,
            "max_wait_minutes": w.max_wait_minutes,
            "distribution": [{"label": b.label, "count": b.count} for b in w.distribution],
        }


def get_pending_investigations(args: m.GetPendingInvestigationsInput) -> dict[str, Any]:
    with unit_of_work() as session:
        _check_department(session, args.department)
        p = queue.get_pending_investigations(session, args.department, args.limit)
        return {
            "data_version": _version(session), "as_of": p.as_of, "filters": {"department": args.department},
            "pending_count": p.pending_count, "avg_age_minutes": p.avg_age_minutes,
            "max_age_minutes": p.max_age_minutes, "avg_delay_minutes": p.avg_delay_minutes,
            "by_facility": [f.model_dump() for f in p.by_facility],
            "items": [
                {
                    "visit_ref": i.visit_ref, "department_code": i.department_code, "facility_code": i.facility_code,
                    "age_minutes": i.age_minutes, "expected_minutes": i.expected_minutes, "delay_minutes": i.delay_minutes,
                }
                for i in p.items
            ],
        }


# ------------------------------------------------------------------ policy retrieval
def _topic_queries(metrics) -> tuple[dict[str, str], dict[str, Any]]:
    """Targeted policy queries that embed the CURRENT metrics (the broad demo question retrieves poorly)."""
    doctors = next((s for s in metrics.staff if s.role == "doctor"), None)
    nurses = next((s for s in metrics.staff if s.role == "nurse"), None)
    used = {
        "patients_waiting": metrics.patients_waiting,
        "avg_wait_minutes": metrics.avg_wait_minutes,
        "available_beds": metrics.beds.available,
        "doctors_available": doctors.available if doctors else None,
        "nurses_available": nurses.available if nurses else None,
        "pending_investigations": metrics.pending_investigations,
    }
    queries = {
        "waiting_time": f"escalation when average waiting time is {metrics.avg_wait_minutes:.0f} minutes "
                        f"and {metrics.patients_waiting} patients are waiting",
        "bed_capacity": f"bed availability with {metrics.beds.available} beds available surge capacity escalation",
        "staffing": f"staffing with {used['doctors_available']} doctors and {used['nurses_available']} nurses available "
                    "resource management shortage",
        "pending_investigations": f"{metrics.pending_investigations} pending investigation requests delays "
                                  "investigation workflow",
        "escalation": "hospital escalation procedure thresholds and responsibilities during surge",
        "discharge": "patient discharge coordination to free beds",
        "registration": "patient registration and admission policy",
    }
    return queries, used


def retrieve_hospital_protocol(args: m.RetrieveHospitalProtocolInput) -> dict[str, Any]:
    with unit_of_work() as session:
        metrics = analytics.get_dashboard_metrics(session)
        version = metrics.data_version
    topic_map, used = _topic_queries(metrics)
    queries = [topic_map[t] for t in args.topics] + list(args.queries)

    best: dict[str, tuple[Any, str]] = {}
    for q in queries:
        for hit in rag.search(q, args.k):
            key = hashlib.sha1(f"{hit.document_name}|{hit.page_number}|{hit.excerpt}".encode()).hexdigest()
            if key not in best or hit.score > best[key][0].score:
                best[key] = (hit, q)
    ranked = sorted(best.values(), key=lambda pair: pair[0].score, reverse=True)[:MAX_POLICY_CHUNKS]

    chunks = [
        {
            "document_name": h.document_name, "page": h.page_number, "score": h.score, "matched_query": q,
            "excerpt": WITHHELD_TEXT if h.injection_flagged else h.excerpt[:EXCERPT_CHARS],
            "flagged": h.injection_flagged,
        }
        for h, q in ranked
    ]
    return {
        "data_version": version, "queries_used": queries,
        "metrics_used": used if args.topics else {},
        "chunks": chunks, "withheld_count": sum(c["flagged"] for c in chunks),
        "context": rag.format_context([h for h, _ in ranked]),
    }


# ------------------------------------------------------------------ management report
def _ratio(numerator: int, denominator: int, noun: str) -> str:
    if denominator == 0:
        return f"{numerator} waiting with no {noun} available"
    return f"{numerator / denominator:.1f} waiting per available {noun}"


def generate_department_report(args: m.GenerateDepartmentReportInput) -> dict[str, Any]:
    """Compose a structured report from verified module data in ONE transaction (consistent snapshot)."""
    with unit_of_work() as session:
        _check_department(session, args.department)
        state = simulation.get_data_state(session)
        waiting = queue.get_waiting_metrics(session, args.department, args.window_minutes)
        pending = queue.get_pending_investigations(session, args.department, 1)
        beds = resources.get_bed_availability(session, args.department)
        staff = resources.get_staff_availability(session, args.department)
        counts = queue.get_visit_counts(session)
        workloads = queue.get_department_workload(session)
        util = analytics.get_resource_utilization(session)

    doctors = next((t for t in staff.totals_by_role if t.role == "doctor"), None)
    nurses = next((t for t in staff.totals_by_role if t.role == "nurse"), None)
    doc_avail = doctors.available if doctors else 0
    flow_obs = [f"{waiting.waiting_patients} patients waiting; average wait {waiting.avg_wait_minutes:.1f} min, "
                f"longest {waiting.max_wait_minutes:.1f} min"]
    flow = {
        "waiting_patients": waiting.waiting_patients, "avg_wait_minutes": waiting.avg_wait_minutes,
        "max_wait_minutes": waiting.max_wait_minutes,
        "distribution": {b.label: b.count for b in waiting.distribution},
    }
    if args.department is None and args.window_minutes is None:
        flow.update(total_visits=counts.total_visits, in_treatment=counts.in_treatment,
                    discharged=counts.discharged, critical_active=counts.critical_active)
        flow_obs.append(f"{counts.critical_active} active patients carry the simulated 'critical' category label")

    cap_obs = [
        f"{beds.available_beds} of {beds.total_beds} beds available ({beds.utilization_pct:.0f}% utilised)",
        _ratio(waiting.waiting_patients, doc_avail, "doctor"),
        _ratio(waiting.waiting_patients, beds.available_beds, "bed"),
    ]
    capacity = {
        "total_beds": beds.total_beds, "occupied_beds": beds.occupied_beds, "available_beds": beds.available_beds,
        "bed_utilization_pct": beds.utilization_pct,
        "doctors": doctors.model_dump() if doctors else None, "nurses": nurses.model_dump() if nurses else None,
    }

    inv_obs = [f"{pending.pending_count} investigations pending; average age {pending.avg_age_minutes:.1f} min, "
               f"average delay beyond expected {pending.avg_delay_minutes:.1f} min"]
    investigations = {
        "pending_count": pending.pending_count, "avg_age_minutes": pending.avg_age_minutes,
        "max_age_minutes": pending.max_age_minutes, "avg_delay_minutes": pending.avg_delay_minutes,
        "by_facility": [f.model_dump() for f in pending.by_facility],
    }
    if util.facilities:
        busiest = max(util.facilities, key=lambda f: f.load_ratio)
        inv_obs.append(f"Highest facility load: {busiest.name} ({busiest.pending_requests} pending, "
                       f"load ratio {busiest.load_ratio:.2f})")

    sections = [
        {"title": "Patient flow", "metrics": flow, "observations": flow_obs},
        {"title": "Capacity", "metrics": capacity, "observations": cap_obs},
        {"title": "Investigations", "metrics": investigations, "observations": inv_obs},
    ]
    if args.department is None and workloads:
        top = max(workloads, key=lambda w: w.total_active)
        sections.append({
            "title": "Department workload",
            "metrics": {w.department_code: {"waiting": w.waiting, "in_treatment": w.in_treatment,
                                            "pending_investigations": w.pending_investigations} for w in workloads},
            "observations": [f"Highest active workload: {top.department_code} ({top.total_active} active, "
                             f"{top.waiting} waiting)"],
        })
    return {
        "data_version": state.data_version, "scenario_name": state.scenario_name, "as_of": waiting.as_of,
        "scope": {"department": args.department, "window_minutes": args.window_minutes},
        "sections": sections,
        "note": "Observations are arithmetic summaries of the verified simulated data. They are not clinical "
                "judgements and do not replace hospital protocols.",
    }
