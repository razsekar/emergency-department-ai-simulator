"""Deterministic, seeded synthetic dataset generator.

Same params + seed + reference_time => identical dataset. All identifiers are fictional
(SIM-PAT-001, SIM-DOC-001, SIM-BED-01, ...). Triage categories are simulated labels used for
data-handling demonstrations only; nothing here is clinical guidance.
"""
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.modules.patient_queue.public import DatasetSpec as QueueDataset
from app.modules.patient_queue.public import InvestigationSpec, VisitSpec
from app.modules.resource_management.public import BedSpec, DepartmentSpec, FacilitySpec, StaffSpec
from app.modules.resource_management.public import DatasetSpec as ResourceDataset
from app.modules.simulation.domain.params import DEPARTMENT_CODES, ScenarioParams

DEPARTMENT_NAMES = {
    "ACUTE": "Acute Care",
    "RESUS": "Resuscitation",
    "MINOR": "Minor Injuries",
    "PEDS": "Pediatric Emergency",
}
# code, name, parallel capacity, expected turnaround minutes, request mix weight
FACILITIES = [
    ("LAB", "Laboratory", 4, 30, 0.45),
    ("XRAY", "X-Ray", 2, 20, 0.25),
    ("CT", "CT Scanner", 1, 45, 0.12),
    ("US", "Ultrasound", 1, 30, 0.18),
]
TRIAGE = ["critical", "urgent", "semi_urgent", "non_urgent"]
TRIAGE_WEIGHTS = [0.09, 0.28, 0.35, 0.28]


@dataclass
class _Visit:
    arrival: datetime
    department: str
    triage: str
    status: str
    started: datetime | None = None
    discharged: datetime | None = None
    bed_ref: str | None = None
    staff_ref: str | None = None
    registered: datetime | None = None


def _apportion(total: int, weights: dict[str, float]) -> dict[str, int]:
    """Largest-remainder allocation of `total` units over weighted buckets (deterministic)."""
    raw = {k: total * w for k, w in weights.items()}
    alloc = {k: int(v) for k, v in raw.items()}
    leftover = total - sum(alloc.values())
    order = sorted(raw, key=lambda k: (-(raw[k] - alloc[k]), list(weights).index(k)))
    for k in order[:leftover]:
        alloc[k] += 1
    return alloc


def _spread_seconds(n: int, mean_minutes: float, rng: random.Random, lo: float = 0.4, hi: float = 1.6) -> list[int]:
    """n positive durations (seconds) spread between lo*mean and hi*mean whose mean is exact."""
    if n == 0:
        return []
    target_total = round(mean_minutes * 60 * n)
    if n == 1:
        return [target_total]
    base = [(lo + (hi - lo) * (i + 0.5) / n) * (1 + rng.uniform(-0.05, 0.05)) for i in range(n)]
    rng.shuffle(base)
    scale = target_total / sum(base)
    values = [max(1, round(b * scale)) for b in base]
    values[-1] = max(1, values[-1] + target_total - sum(values))
    return values


def generate(params: ScenarioParams, reference_time: datetime) -> tuple[ResourceDataset, QueueDataset]:
    rng = random.Random(params.seed)
    ref = reference_time
    weights = params.normalized_workload()
    codes = list(DEPARTMENT_CODES)
    wlist = [weights[c] for c in codes]

    # ---- beds -------------------------------------------------------------------------
    total_beds = params.beds_available + params.beds_occupied
    bed_alloc = _apportion(total_beds, weights)
    bed_depts = [c for c in codes for _ in range(bed_alloc[c])]
    occupied_idx = set(rng.sample(range(total_beds), params.beds_occupied))
    beds = [
        BedSpec(ref=f"SIM-BED-{i + 1:02d}", department_code=d, status="occupied" if i in occupied_idx else "available")
        for i, d in enumerate(bed_depts)
    ]

    # ---- staff ------------------------------------------------------------------------
    utilisation = params.beds_occupied / total_beds
    staff: list[StaffSpec] = []
    busy_doctors: list[str] = []
    for role, prefix, count in (
        ("doctor", "DOC", params.doctors_on_duty),
        ("nurse", "NUR", params.nurses_on_duty),
    ):
        depts = [c for c, n in _apportion(count, weights).items() for _ in range(n)]
        busy_n = min(count, int(count * utilisation + 0.5))
        busy_idx = set(rng.sample(range(count), busy_n))
        for i, d in enumerate(depts):
            ref_id = f"SIM-{prefix}-{i + 1:03d}"
            status = "busy" if i in busy_idx else "available"
            staff.append(StaffSpec(ref=ref_id, role=role, department_code=d, status=status))
            if role == "doctor" and status == "busy":
                busy_doctors.append(ref_id)

    departments = [
        DepartmentSpec(code=c, name=DEPARTMENT_NAMES[c], capacity=bed_alloc[c], workload_weight=round(weights[c], 4))
        for c in codes
    ]
    facilities = [
        FacilitySpec(code=c, name=n, capacity=cap, expected_minutes=exp) for c, n, cap, exp, _ in FACILITIES
    ]

    # ---- visits -----------------------------------------------------------------------
    visits: list[_Visit] = []
    occupied_beds = [b for b in beds if b.status == "occupied"]

    for wait_s in _spread_seconds(params.waiting_patients, params.avg_wait_minutes, rng):
        arrival = ref - timedelta(seconds=wait_s)
        reg = arrival + timedelta(seconds=min(wait_s // 2, rng.randint(60, 300)))
        visits.append(_Visit(arrival, rng.choices(codes, wlist)[0], rng.choices(TRIAGE, TRIAGE_WEIGHTS)[0],
                             "waiting", registered=reg))

    for i, bed in enumerate(occupied_beds):
        started = ref - timedelta(minutes=rng.uniform(10, 120))
        arrival = started - timedelta(minutes=params.avg_wait_minutes * rng.uniform(0.5, 1.5))
        reg = arrival + timedelta(minutes=rng.uniform(1, 5))
        staff_ref = busy_doctors[i % len(busy_doctors)] if busy_doctors else None
        visits.append(_Visit(arrival, bed.department_code, rng.choices(TRIAGE, TRIAGE_WEIGHTS)[0], "in_treatment",
                             started=started, bed_ref=bed.ref, staff_ref=staff_ref, registered=reg))

    expected_arrivals = round(params.arrival_rate_per_hour * params.window_minutes / 60)
    discharged_n = max(0, expected_arrivals - params.waiting_patients - params.beds_occupied)
    for _ in range(discharged_n):
        wait = timedelta(minutes=params.avg_wait_minutes * rng.uniform(0.5, 1.5))
        stay = timedelta(minutes=rng.uniform(30, 150))
        latest = ref - wait - stay - timedelta(minutes=1)
        earliest = ref - timedelta(minutes=params.window_minutes)
        arrival = earliest + (latest - earliest) * rng.random() if latest > earliest else earliest
        started = arrival + wait
        discharged = min(started + stay, ref - timedelta(minutes=1))
        reg = arrival + timedelta(minutes=rng.uniform(1, 5))
        visits.append(_Visit(arrival, rng.choices(codes, wlist)[0], rng.choices(TRIAGE, TRIAGE_WEIGHTS)[0],
                             "discharged", started=started, discharged=discharged, registered=reg))

    visits.sort(key=lambda v: v.arrival)
    refs = {id(v): f"SIM-VIS-{i + 1:04d}" for i, v in enumerate(visits)}
    visit_specs = [
        VisitSpec(
            visit_ref=refs[id(v)], patient_ref=f"SIM-PAT-{i + 1:03d}", arrival_at=v.arrival,
            registered_at=v.registered, department_code=v.department, triage_category=v.triage, status=v.status,
            treatment_started_at=v.started, assigned_staff_ref=v.staff_ref, bed_ref=v.bed_ref,
            discharged_at=v.discharged,
        )
        for i, v in enumerate(visits)
    ]

    # ---- investigations ---------------------------------------------------------------
    fac_codes = [f[0] for f in FACILITIES]
    fac_weights = [f[4] for f in FACILITIES]
    expected_by_code = {f[0]: f[3] for f in FACILITIES}
    investigations: list[InvestigationSpec] = []

    def _fac() -> str:
        return rng.choices(fac_codes, fac_weights)[0]

    active = sorted((v for v in visits if v.status != "discharged"), key=lambda v: v.arrival)  # oldest first
    ages = sorted(_spread_seconds(params.pending_investigations, params.investigation_delay_minutes, rng, 0.3, 1.7),
                  reverse=True)
    for age_s, v in zip(ages, active):  # oldest requests belong to the longest-present patients
        age_s = min(age_s, max(60, int((ref - v.arrival).total_seconds()) - 60))
        code = _fac()
        investigations.append(InvestigationSpec(
            visit_ref=refs[id(v)], facility_code=code, investigation_type=code, status="pending",
            requested_at=ref - timedelta(seconds=age_s), expected_minutes=expected_by_code[code]))

    for v in visits:
        if v.status == "waiting" or v.started is None or rng.random() >= 0.45:
            continue
        code = _fac()
        exp = expected_by_code[code]
        requested = v.started + timedelta(minutes=rng.uniform(2, 15))
        completed = requested + timedelta(minutes=exp * rng.uniform(0.7, 1.4))
        upper = v.discharged or (ref - timedelta(minutes=1))
        if completed > upper:
            continue
        investigations.append(InvestigationSpec(
            visit_ref=refs[id(v)], facility_code=code, investigation_type=code, status="completed",
            requested_at=requested, completed_at=completed, expected_minutes=exp))

    return (
        ResourceDataset(departments=departments, staff=staff, beds=beds, facilities=facilities),
        QueueDataset(reference_time=ref, visits=visit_specs, investigations=investigations),
    )
