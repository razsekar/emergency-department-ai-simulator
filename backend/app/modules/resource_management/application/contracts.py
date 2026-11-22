"""Typed request/response contracts of the resource_management module."""
from typing import Literal

from pydantic import BaseModel, ConfigDict

StaffRole = Literal["doctor", "nurse"]
StaffStatus = Literal["available", "busy", "off_duty"]
BedStatus = Literal["available", "occupied"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


# ---- dataset specs (written by the simulation module through public.replace_dataset) ----
class DepartmentSpec(_Frozen):
    code: str
    name: str
    capacity: int
    workload_weight: float


class StaffSpec(_Frozen):
    ref: str
    role: StaffRole
    department_code: str
    status: StaffStatus


class BedSpec(_Frozen):
    ref: str
    department_code: str
    status: BedStatus


class FacilitySpec(_Frozen):
    code: str
    name: str
    capacity: int
    expected_minutes: int


class DatasetSpec(_Frozen):
    departments: list[DepartmentSpec]
    staff: list[StaffSpec]
    beds: list[BedSpec]
    facilities: list[FacilitySpec]


# ---- read models ----
class DepartmentBeds(BaseModel):
    department_code: str
    department_name: str
    total_beds: int
    occupied_beds: int
    available_beds: int
    utilization_pct: float


class BedAvailability(BaseModel):
    total_beds: int
    occupied_beds: int
    available_beds: int
    utilization_pct: float
    by_department: list[DepartmentBeds]


class StaffGroup(BaseModel):
    department_code: str
    role: StaffRole
    on_duty: int
    available: int
    busy: int


class RoleTotals(BaseModel):
    role: StaffRole
    on_duty: int
    available: int
    busy: int
    utilization_pct: float


class StaffAvailability(BaseModel):
    on_duty: int
    available: int
    busy: int
    totals_by_role: list[RoleTotals]
    groups: list[StaffGroup]


class DepartmentCapacity(BaseModel):
    department_code: str
    department_name: str
    bed_capacity: int
    occupied_beds: int
    doctors_on_duty: int
    nurses_on_duty: int
    workload_weight: float
    bed_utilization_pct: float


class Facility(BaseModel):
    code: str
    name: str
    capacity: int
    expected_minutes: int


class BedRow(BaseModel):
    ref: str
    department_code: str
    status: BedStatus


class StaffRow(BaseModel):
    ref: str
    role: StaffRole
    department_code: str
    status: StaffStatus


class BedPage(BaseModel):
    items: list[BedRow]
    total: int
    page: int
    page_size: int


class StaffPage(BaseModel):
    items: list[StaffRow]
    total: int
    page: int
    page_size: int
