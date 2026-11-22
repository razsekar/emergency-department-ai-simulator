"""Use cases of the resource_management module."""
from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy.orm import Session

from app.modules.resource_management.application import contracts as c
from app.modules.resource_management.infrastructure import repository as repo
from app.platform.db import unit_of_work

T = TypeVar("T")


def run(fn: Callable[..., T], /, **kwargs: Any) -> T:
    """Execute a use case in its own transaction (used by API controllers)."""
    with unit_of_work() as session:
        return fn(session, **kwargs)


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def replace_dataset(session: Session, spec: c.DatasetSpec) -> None:
    repo.replace_dataset(session, spec)


def get_bed_availability(session: Session, department_code: str | None = None) -> c.BedAvailability:
    rows = repo.bed_counts(session, department_code)
    by_dept = [
        c.DepartmentBeds(
            department_code=r.code,
            department_name=r.name,
            total_beds=r.total,
            occupied_beds=r.occupied,
            available_beds=r.total - r.occupied,
            utilization_pct=_pct(r.occupied, r.total),
        )
        for r in rows
    ]
    total = sum(d.total_beds for d in by_dept)
    occupied = sum(d.occupied_beds for d in by_dept)
    return c.BedAvailability(
        total_beds=total,
        occupied_beds=occupied,
        available_beds=total - occupied,
        utilization_pct=_pct(occupied, total),
        by_department=by_dept,
    )


def get_staff_availability(
    session: Session, department_code: str | None = None, role: str | None = None
) -> c.StaffAvailability:
    rows = repo.staff_counts(session, department_code, role)
    groups = [
        c.StaffGroup(department_code=r.code, role=r.role, on_duty=r.on_duty, available=r.available, busy=r.busy)
        for r in rows
    ]
    totals: dict[str, list[int]] = {}
    for g in groups:
        t = totals.setdefault(g.role, [0, 0, 0])
        t[0] += g.on_duty
        t[1] += g.available
        t[2] += g.busy
    by_role = [
        c.RoleTotals(role=role, on_duty=t[0], available=t[1], busy=t[2], utilization_pct=_pct(t[2], t[0]))
        for role, t in sorted(totals.items())
    ]
    return c.StaffAvailability(
        on_duty=sum(g.on_duty for g in groups),
        available=sum(g.available for g in groups),
        busy=sum(g.busy for g in groups),
        totals_by_role=by_role,
        groups=groups,
    )


def get_department_capacity(session: Session) -> list[c.DepartmentCapacity]:
    beds = {b.department_code: b for b in get_bed_availability(session).by_department}
    staff = get_staff_availability(session).groups
    result = []
    for d in repo.department_rows(session):
        doctors = sum(g.on_duty for g in staff if g.department_code == d.code and g.role == "doctor")
        nurses = sum(g.on_duty for g in staff if g.department_code == d.code and g.role == "nurse")
        b = beds.get(d.code)
        result.append(
            c.DepartmentCapacity(
                department_code=d.code,
                department_name=d.name,
                bed_capacity=d.capacity,
                occupied_beds=b.occupied_beds if b else 0,
                doctors_on_duty=doctors,
                nurses_on_duty=nurses,
                workload_weight=d.workload_weight,
                bed_utilization_pct=b.utilization_pct if b else 0.0,
            )
        )
    return result


def list_facilities(session: Session) -> list[c.Facility]:
    return [
        c.Facility(code=r.code, name=r.name, capacity=r.capacity, expected_minutes=r.expected_minutes)
        for r in repo.facility_rows(session)
    ]


def list_beds(
    session: Session, department_code: str | None = None, status: str | None = None, page: int = 1,
    page_size: int = 50,
) -> c.BedPage:
    total, rows = repo.list_beds(session, department_code, status, page_size, (page - 1) * page_size)
    return c.BedPage(
        items=[c.BedRow(ref=r.ref, department_code=r.department_code, status=r.status) for r in rows],
        total=total, page=page, page_size=page_size,
    )


def list_staff(
    session: Session, department_code: str | None = None, role: str | None = None, status: str | None = None,
    page: int = 1, page_size: int = 50,
) -> c.StaffPage:
    total, rows = repo.list_staff(session, department_code, role, status, page_size, (page - 1) * page_size)
    return c.StaffPage(
        items=[
            c.StaffRow(ref=r.ref, role=r.role, department_code=r.department_code, status=r.status) for r in rows
        ],
        total=total, page=page, page_size=page_size,
    )
