/** Typed mirrors of backend/app/modules/resource_management/application/contracts.py. */

export type StaffRole = 'doctor' | 'nurse';
export type StaffStatus = 'available' | 'busy' | 'off_duty';
export type BedStatus = 'available' | 'occupied';

export interface DepartmentBeds {
  department_code: string;
  department_name: string;
  total_beds: number;
  occupied_beds: number;
  available_beds: number;
  utilization_pct: number;
}

export interface BedAvailability {
  total_beds: number;
  occupied_beds: number;
  available_beds: number;
  utilization_pct: number;
  by_department: DepartmentBeds[];
}

export interface RoleTotals {
  role: StaffRole;
  on_duty: number;
  available: number;
  busy: number;
  utilization_pct: number;
}

export interface StaffGroup {
  department_code: string;
  role: StaffRole;
  on_duty: number;
  available: number;
  busy: number;
}

export interface StaffAvailability {
  on_duty: number;
  available: number;
  busy: number;
  totals_by_role: RoleTotals[];
  groups: StaffGroup[];
}

export interface DepartmentCapacity {
  department_code: string;
  department_name: string;
  bed_capacity: number;
  occupied_beds: number;
  doctors_on_duty: number;
  nurses_on_duty: number;
  workload_weight: number;
  bed_utilization_pct: number;
}

export interface Facility {
  code: string;
  name: string;
  capacity: number;
  expected_minutes: number;
}

export interface BedRow {
  ref: string;
  department_code: string;
  status: BedStatus;
}

export interface StaffRow {
  ref: string;
  role: StaffRole;
  department_code: string;
  status: StaffStatus;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface BedFilter {
  department?: string;
  status?: BedStatus;
  page?: number;
  pageSize?: number;
}

export interface StaffFilter {
  department?: string;
  role?: StaffRole;
  status?: StaffStatus;
  page?: number;
  pageSize?: number;
}
