/** Typed mirrors of backend/app/modules/simulation/application/schemas.py and domain/params.py. */

export type ScenarioKey = 'normal' | 'surge' | 'recovery' | 'custom';

export const DEPARTMENT_CODES = ['ACUTE', 'RESUS', 'MINOR', 'PEDS'] as const;

export interface ScenarioParams {
  seed: number;
  arrival_rate_per_hour: number;
  beds_available: number;
  beds_occupied: number;
  doctors_on_duty: number;
  nurses_on_duty: number;
  waiting_patients: number;
  avg_wait_minutes: number;
  pending_investigations: number;
  investigation_delay_minutes: number;
  department_workload: Record<string, number>;
  window_minutes: number;
}

export type ScenarioOverrides = Partial<ScenarioParams>;

export interface ScenarioInfo {
  key: string;
  name: string;
  description: string;
  is_builtin: boolean;
  is_current: boolean;
  parameters: ScenarioParams;
}

export interface DataState {
  data_version: number;
  scenario_key: string | null;
  scenario_name: string | null;
  applied_at: string | null;
  last_run_id: string | null;
}

export interface ScenarioRunInfo {
  id: string;
  scenario_key: string;
  scenario_name: string;
  trigger: string;
  status: string;
  data_version: number | null;
  parameters: Record<string, unknown>;
  validation: Record<string, unknown>[] | null;
  error: string | null;
  record_count: number;
  duration_ms: number;
  created_at: string;
}

export interface ApplyResponse {
  state: DataState;
  run: ScenarioRunInfo;
}

export interface RunPage {
  items: ScenarioRunInfo[];
  total: number;
  limit: number;
  offset: number;
}
