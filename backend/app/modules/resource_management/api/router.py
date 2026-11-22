"""HTTP endpoints for resource management. Controllers delegate to application use cases."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.modules.resource_management.application import contracts as c
from app.modules.resource_management.application import service
from app.modules.identity.public import Permission, require_permission

router = APIRouter(
    prefix="/api/resources", tags=["resources"],
    dependencies=[Depends(require_permission(Permission.RESOURCES_READ))],
)

Department = Annotated[str | None, Query(description="Department code, e.g. ACUTE")]


@router.get("/beds/availability", response_model=c.BedAvailability)
def bed_availability(department: Department = None) -> c.BedAvailability:
    return service.run(service.get_bed_availability, department_code=department)


@router.get("/staff/availability", response_model=c.StaffAvailability)
def staff_availability(
    department: Department = None, role: Annotated[c.StaffRole | None, Query()] = None
) -> c.StaffAvailability:
    return service.run(service.get_staff_availability, department_code=department, role=role)


@router.get("/departments", response_model=list[c.DepartmentCapacity])
def departments() -> list[c.DepartmentCapacity]:
    return service.run(service.get_department_capacity)


@router.get("/facilities", response_model=list[c.Facility])
def facilities() -> list[c.Facility]:
    return service.run(service.list_facilities)


@router.get("/beds", response_model=c.BedPage)
def beds(
    department: Department = None,
    status: Annotated[c.BedStatus | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> c.BedPage:
    return service.run(
        service.list_beds, department_code=department, status=status, page=page, page_size=page_size
    )


@router.get("/staff", response_model=c.StaffPage)
def staff(
    department: Department = None,
    role: Annotated[c.StaffRole | None, Query()] = None,
    status: Annotated[c.StaffStatus | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> c.StaffPage:
    return service.run(
        service.list_staff, department_code=department, role=role, status=status, page=page,
        page_size=page_size,
    )
