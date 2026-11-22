import { DashboardMetrics } from '../dashboard/dashboard.models';
import { ApplyResponse, ScenarioInfo, ScenarioParams } from '../simulator/simulator.models';

export const NORMAL_PARAMS: ScenarioParams = {
  seed: 1001,
  arrival_rate_per_hour: 8,
  beds_available: 8,
  beds_occupied: 10,
  doctors_on_duty: 6,
  nurses_on_duty: 10,
  waiting_patients: 12,
  avg_wait_minutes: 15,
  pending_investigations: 5,
  investigation_delay_minutes: 20,
  department_workload: { ACUTE: 0.4, RESUS: 0.1, MINOR: 0.3, PEDS: 0.2 },
  window_minutes: 240,
};

export const SCENARIO_LIST: ScenarioInfo[] = [
  { key: 'normal', name: 'Normal Operations', description: 'n', is_builtin: true, is_current: false, parameters: NORMAL_PARAMS },
  {
    key: 'surge',
    name: 'Emergency Surge',
    description: 's',
    is_builtin: true,
    is_current: false,
    parameters: { ...NORMAL_PARAMS, seed: 2002, arrival_rate_per_hour: 25, beds_available: 1, waiting_patients: 38 },
  },
];

export function applyResponse(key: string, name: string, version: number): ApplyResponse {
  return {
    state: { data_version: version, scenario_key: key, scenario_name: name, applied_at: '2026-11-22T08:00:00Z', last_run_id: 'r1' },
    run: {
      id: 'r1',
      scenario_key: key,
      scenario_name: name,
      trigger: 'apply',
      status: 'success',
      data_version: version,
      parameters: {},
      validation: null,
      error: null,
      record_count: 100,
      duration_ms: 12,
      created_at: '2026-11-22T08:00:00Z',
    },
  };
}

export function metrics(over: Partial<DashboardMetrics> = {}): DashboardMetrics {
  return {
    data_version: 1,
    scenario_key: 'normal',
    scenario_name: 'Normal Operations',
    as_of: '2026-11-22T08:00:00Z',
    total_visits: 40,
    patients_waiting: 12,
    patients_in_treatment: 10,
    completed_discharges: 18,
    critical_patients: 3,
    beds: { total: 18, occupied: 10, available: 8, utilization_pct: 55.6 },
    staff: [
      { role: 'doctor', on_duty: 6, available: 2, busy: 4, utilization_pct: 66.7 },
      { role: 'nurse', on_duty: 10, available: 3, busy: 7, utilization_pct: 70 },
    ],
    avg_wait_minutes: 15,
    max_wait_minutes: 24.8,
    pending_investigations: 5,
    avg_pending_investigation_age_minutes: 20,
    avg_pending_investigation_delay_minutes: 4,
    department_workload: [
      { department_code: 'ACUTE', waiting: 5, in_treatment: 4, pending_investigations: 2, total_active: 9 },
      { department_code: 'MINOR', waiting: 7, in_treatment: 6, pending_investigations: 3, total_active: 13 },
    ],
    arrivals_over_time: [
      { bucket_start: '2026-11-22T06:00:00Z', count: 4 },
      { bucket_start: '2026-11-22T06:30:00Z', count: 6 },
    ],
    waiting_time_distribution: [
      { label: '0-15', min_minutes: 0, max_minutes: 15, count: 6 },
      { label: '15-30', min_minutes: 15, max_minutes: 30, count: 6 },
    ],
    resource_utilization: {
      data_version: 1,
      beds_pct: 55.6,
      doctors_pct: 66.7,
      nurses_pct: 70,
      facilities: [
        { code: 'LAB', name: 'Laboratory', capacity: 4, pending_requests: 2, load_ratio: 0.5, avg_age_minutes: 18 },
      ],
      departments: [],
    },
    ...over,
  };
}
