import { RetrievedPolicyView, ToolExecutionView } from '../agent/agent.models';
import { ProviderName, Usage } from '../playground/providers.service';

/**
 * Mirrors backend/app/modules/ai_orchestration/application/demo_contracts.py.
 * The demonstration question is fixed by the backend; the presenter only picks the scenario and the model.
 */
export type DemoScenario = 'normal' | 'surge' | 'recovery';
export type DemoAgentMode = 'auto' | 'native' | 'fallback';

export interface DemoStepRequest {
  scenario: DemoScenario;
  provider: ProviderName;
  model: string;
  temperature?: number | null;
  mode?: DemoAgentMode;
}

export interface MetricChange {
  metric: string;
  before: unknown;
  after: unknown;
}

/** Evidence that the underlying records changed before the question was asked. */
export interface StepVerification {
  data_version_before: number;
  data_version_after: number;
  data_version_changed: boolean;
  compared_to: 'previous_run' | 'state_before_step';
  metrics_changed: boolean;
  changed_metrics: MetricChange[];
  question_identical: boolean;
  analysis_data_version_matches: boolean;
  note: string | null;
}

export interface DemoRunView {
  id: string;
  session_id: string;
  run_number: number;
  run_label: string;
  analysis_run_id: string | null;
  scenario_key: string | null;
  scenario_name: string | null;
  data_version: number;
  patient_record_count: number;
  metrics: Record<string, unknown>;
  verification: StepVerification | null;
  tools_executed: ToolExecutionView[];
  retrieved_policies: RetrievedPolicyView[];
  question: string;
  question_sha256: string;
  final_answer: string | null;
  provider: string;
  model: string;
  latency_ms: number;
  usage: Usage;
  estimated_cost_usd: number | null;
  created_by: string;
  created_at: string;
}

export interface MetricComparisonRow {
  metric: string;
  values: unknown[];
  differs: boolean;
  deltas_vs_previous: (number | null)[];
}

export interface DemoSessionView {
  session_id: string | null;
  question: string;
  question_sha256: string;
  run_count: number;
  runs: DemoRunView[];
  metric_comparison: MetricComparisonRow[];
}

export interface DemoStepResponse {
  run: DemoRunView;
  run_count: number;
  metric_comparison: MetricComparisonRow[];
}

export interface DemoResetResponse {
  cleared_runs: number;
  baseline_scenario: string;
  data_version: number;
}

export const DEMO_STEPS: readonly { key: DemoScenario; label: string; button: string; icon: string }[] = [
  { key: 'normal', label: 'Normal Operations', button: 'Load Normal and Ask', icon: 'check_circle' },
  { key: 'surge', label: 'Emergency Surge', button: 'Load Surge and Ask', icon: 'crisis_alert' },
  { key: 'recovery', label: 'Recovery Operations', button: 'Load Recovery and Ask', icon: 'trending_down' },
];
