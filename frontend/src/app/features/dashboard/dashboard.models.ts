/** Typed mirrors of backend/app/modules/analytics/application/contracts.py (and patient_queue read models). */

export interface BedSummary {
  total: number;
  occupied: number;
  available: number;
  utilization_pct: number;
}

export interface StaffSummary {
  role: string;
  on_duty: number;
  available: number;
  busy: number;
  utilization_pct: number;
}

export interface FacilityLoad {
  code: string;
  name: string;
  capacity: number;
  pending_requests: number;
  load_ratio: number;
  avg_age_minutes: number;
}

export interface ResourceUtilization {
  data_version: number;
  beds_pct: number;
  doctors_pct: number;
  nurses_pct: number;
  facilities: FacilityLoad[];
  departments: Record<string, unknown>[];
}

export interface DepartmentWorkload {
  department_code: string;
  waiting: number;
  in_treatment: number;
  pending_investigations: number;
  total_active: number;
}

export interface ArrivalPoint {
  bucket_start: string;
  count: number;
}

export interface WaitBucket {
  label: string;
  min_minutes: number;
  max_minutes: number | null;
  count: number;
}

export interface DashboardMetrics {
  data_version: number;
  scenario_key: string | null;
  scenario_name: string | null;
  as_of: string | null;
  total_visits: number;
  patients_waiting: number;
  patients_in_treatment: number;
  completed_discharges: number;
  critical_patients: number;
  beds: BedSummary;
  staff: StaffSummary[];
  avg_wait_minutes: number;
  max_wait_minutes: number;
  pending_investigations: number;
  avg_pending_investigation_age_minutes: number;
  avg_pending_investigation_delay_minutes: number;
  department_workload: DepartmentWorkload[];
  arrivals_over_time: ArrivalPoint[];
  waiting_time_distribution: WaitBucket[];
  resource_utilization: ResourceUtilization;
}
