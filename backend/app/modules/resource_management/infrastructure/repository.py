"""Persistence for resource_management. Only this module touches its tables."""
import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.resource_management.infrastructure.tables import beds, departments, facilities, staff

ON_DUTY = ("available", "busy")


def replace_dataset(session: Session, spec: Any) -> None:
    for table in (beds, staff, facilities, departments):
        session.execute(sa.delete(table))
    dept_ids = {d.code: uuid.uuid4() for d in spec.departments}
    if spec.departments:
        session.execute(
            sa.insert(departments),
            [
                {"id": dept_ids[d.code], "code": d.code, "name": d.name, "capacity": d.capacity,
                 "workload_weight": d.workload_weight}
                for d in spec.departments
            ],
        )
    if spec.staff:
        session.execute(
            sa.insert(staff),
            [
                {"ref": s.ref, "role": s.role, "department_id": dept_ids[s.department_code], "status": s.status}
                for s in spec.staff
            ],
        )
    if spec.beds:
        session.execute(
            sa.insert(beds),
            [{"ref": b.ref, "department_id": dept_ids[b.department_code], "status": b.status} for b in spec.beds],
        )
    if spec.facilities:
        session.execute(
            sa.insert(facilities),
            [
                {"code": f.code, "name": f.name, "capacity": f.capacity, "expected_minutes": f.expected_minutes}
                for f in spec.facilities
            ],
        )


def bed_counts(session: Session, department_code: str | None) -> list[sa.Row]:
    q = (
        sa.select(
            departments.c.code,
            departments.c.name,
            sa.func.count(beds.c.id).label("total"),
            sa.func.count(beds.c.id).filter(beds.c.status == "occupied").label("occupied"),
        )
        .select_from(departments.outerjoin(beds, beds.c.department_id == departments.c.id))
        .group_by(departments.c.id)
        .order_by(departments.c.code)
    )
    if department_code:
        q = q.where(departments.c.code == department_code)
    return list(session.execute(q))


def staff_counts(session: Session, department_code: str | None, role: str | None) -> list[sa.Row]:
    q = (
        sa.select(
            departments.c.code,
            staff.c.role,
            sa.func.count(staff.c.id).filter(staff.c.status.in_(ON_DUTY)).label("on_duty"),
            sa.func.count(staff.c.id).filter(staff.c.status == "available").label("available"),
            sa.func.count(staff.c.id).filter(staff.c.status == "busy").label("busy"),
        )
        .select_from(staff.join(departments, staff.c.department_id == departments.c.id))
        .group_by(departments.c.code, staff.c.role)
        .order_by(departments.c.code, staff.c.role)
    )
    if department_code:
        q = q.where(departments.c.code == department_code)
    if role:
        q = q.where(staff.c.role == role)
    return list(session.execute(q))


def department_rows(session: Session) -> list[sa.Row]:
    return list(session.execute(sa.select(departments).order_by(departments.c.code)))


def facility_rows(session: Session) -> list[sa.Row]:
    return list(session.execute(sa.select(facilities).order_by(facilities.c.code)))


def list_beds(session: Session, department_code: str | None, status: str | None, limit: int, offset: int):
    base = sa.select(beds.c.ref, departments.c.code.label("department_code"), beds.c.status).select_from(
        beds.join(departments, beds.c.department_id == departments.c.id)
    )
    if department_code:
        base = base.where(departments.c.code == department_code)
    if status:
        base = base.where(beds.c.status == status)
    total = session.execute(sa.select(sa.func.count()).select_from(base.subquery())).scalar_one()
    rows = session.execute(base.order_by(beds.c.ref).limit(limit).offset(offset)).all()
    return total, rows


def list_staff(
    session: Session, department_code: str | None, role: str | None, status: str | None, limit: int, offset: int
):
    base = sa.select(
        staff.c.ref, staff.c.role, departments.c.code.label("department_code"), staff.c.status
    ).select_from(staff.join(departments, staff.c.department_id == departments.c.id))
    if department_code:
        base = base.where(departments.c.code == department_code)
    if role:
        base = base.where(staff.c.role == role)
    if status:
        base = base.where(staff.c.status == status)
    total = session.execute(sa.select(sa.func.count()).select_from(base.subquery())).scalar_one()
    rows = session.execute(base.order_by(staff.c.ref).limit(limit).offset(offset)).all()
    return total, rows
