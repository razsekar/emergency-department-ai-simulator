"""Public interface of the resource_management module. Other modules may import ONLY this file.

Contracts (all typed, all take an open SQLAlchemy ``session`` so callers control the transaction):

  replace_dataset(session, DatasetSpec)                    -> None   (used by the simulation module)
  get_bed_availability(session, department_code=None)      -> BedAvailability
  get_staff_availability(session, department_code=None, role=None) -> StaffAvailability
  get_department_capacity(session)                         -> list[DepartmentCapacity]
  list_facilities(session)                                 -> list[Facility]
  list_beds / list_staff (paginated)                       -> BedPage / StaffPage

This module owns the schema ``resource_management``; nobody else may read or write its tables.
"""
from app.modules.resource_management.application.contracts import (
    BedAvailability,
    BedPage,
    BedSpec,
    DatasetSpec,
    DepartmentBeds,
    DepartmentCapacity,
    DepartmentSpec,
    Facility,
    FacilitySpec,
    RoleTotals,
    StaffAvailability,
    StaffGroup,
    StaffPage,
    StaffSpec,
)
from app.modules.resource_management.application.service import (
    get_bed_availability,
    get_department_capacity,
    get_staff_availability,
    list_beds,
    list_facilities,
    list_staff,
    replace_dataset,
)

__all__ = [
    "BedAvailability", "BedPage", "BedSpec", "DatasetSpec", "DepartmentBeds", "DepartmentCapacity",
    "DepartmentSpec", "Facility", "FacilitySpec", "RoleTotals", "StaffAvailability", "StaffGroup",
    "StaffPage", "StaffSpec", "get_bed_availability", "get_department_capacity", "get_staff_availability",
    "list_beds", "list_facilities", "list_staff", "replace_dataset",
]
