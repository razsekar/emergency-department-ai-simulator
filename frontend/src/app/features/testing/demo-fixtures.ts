import { ComparisonHistoryPage, ComparisonRunResponse, ModelResultView } from '../comparison/comparison.models';
import { DemoRunView, DemoSessionView, MetricComparisonRow, StepVerification } from '../demo/demo.models';
import { ModelInfo, ProviderStatus } from '../playground/providers.service';

export const FIXED_QUESTION =
  'Analyze the current emergency department situation. Identify operational bottlenecks, waiting-time issues, resource shortages and recommended administrative actions.';

export const DEMO_STATUSES: ProviderStatus[] = [
  { provider: 'ollama', label: 'Ollama (local)', configured: true, reachable: true, cloud: false, data_disclosure: null, detail: 'reachable' },
  { provider: 'openai', label: 'OpenAI', configured: false, reachable: null, cloud: true, data_disclosure: 'Prompts are sent to OpenAI.', detail: 'Set OPENAI_API_KEY on the backend.' },
];

export const DEMO_MODELS: ModelInfo[] = [
  { provider: 'ollama', model_id: 'model-a', display_name: 'model-a', source: 'discovered', supports_tools: true, cloud: false },
  { provider: 'ollama', model_id: 'model-b', display_name: 'model-b', source: 'discovered', supports_tools: false, cloud: false },
  { provider: 'openai', model_id: 'cloud-model', display_name: 'cloud-model', source: 'env', supports_tools: null, cloud: true },
];

const VERIFICATION: StepVerification = {
  data_version_before: 1,
  data_version_after: 2,
  data_version_changed: true,
  compared_to: 'previous_run',
  metrics_changed: true,
  changed_metrics: [{ metric: 'patients_waiting', before: 12, after: 38 }],
  question_identical: true,
  analysis_data_version_matches: true,
  note: null,
};

export function demoRun(n: number, key: 'normal' | 'surge' | 'recovery', overrides: Partial<DemoRunView> = {}): DemoRunView {
  const names = { normal: 'Normal Operations', surge: 'Emergency Surge', recovery: 'Recovery Operations' };
  const waiting = { normal: 12, surge: 38, recovery: 9 }[key];
  return {
    id: `demo-${n}`,
    session_id: 'sess-1',
    run_number: n,
    run_label: `Run ${n}`,
    analysis_run_id: `analysis-${n}`,
    scenario_key: key,
    scenario_name: names[key],
    data_version: n,
    patient_record_count: 100 + n,
    metrics: { patients_waiting: waiting, avg_wait_minutes: key === 'surge' ? 75 : 15 },
    verification: { ...VERIFICATION, data_version_before: n - 1, data_version_after: n, metrics_changed: n > 1 },
    tools_executed: [
      { sequence: 1, tool_name: 'get_bed_availability', status: 'ok', arguments: {}, output: { available: key === 'surge' ? 1 : 8 }, error: null, duration_ms: 11, data_version: n },
    ],
    retrieved_policies: [
      { document_name: 'Hospital Escalation Procedures', page: 2, score: 0.81, excerpt: 'Escalate when average wait exceeds 60 minutes.', matched_query: 'wait', flagged: false },
    ],
    question: FIXED_QUESTION,
    question_sha256: 'a'.repeat(64),
    final_answer: `There are ${waiting} patients waiting [Source: Hospital Escalation Procedures, p.2].\n\nGeneral note without a policy citation.`,
    provider: 'ollama',
    model: 'model-a',
    latency_ms: 1200 + n,
    usage: { prompt_tokens: 100, completion_tokens: 50, total_tokens: 150 },
    estimated_cost_usd: null,
    created_by: 'demo_presenter',
    created_at: '2026-11-22T10:00:00Z',
    ...overrides,
  };
}

export function metricRows(runs: DemoRunView[]): MetricComparisonRow[] {
  return ['patients_waiting', 'avg_wait_minutes'].map((metric) => {
    const values = runs.map((r) => r.metrics[metric]);
    return {
      metric,
      values,
      differs: new Set(values).size > 1,
      deltas_vs_previous: values.map((v, i) => (i === 0 ? null : (v as number) - (values[i - 1] as number))),
    };
  });
}

export function demoSession(runs: DemoRunView[]): DemoSessionView {
  return {
    session_id: runs.length ? 'sess-1' : null,
    question: FIXED_QUESTION,
    question_sha256: 'a'.repeat(64),
    run_count: runs.length,
    runs,
    metric_comparison: metricRows(runs),
  };
}

export const CHECK_OK = {
  citations: [{ document: 'Hospital Escalation Procedures', page: 2, verified: true }],
  verified_count: 1,
  unverified_count: 0,
  unverified: [],
  retrieved_count: 1,
};

export function modelResult(position: number, overrides: Partial<ModelResultView> = {}): ModelResultView {
  return {
    position,
    provider: 'ollama',
    model: position === 1 ? 'model-a' : 'model-b',
    temperature: null,
    status: 'completed',
    error: null,
    answer: 'Waiting is high at 38 [Source: Hospital Escalation Procedures, p.2].\n\nExplanation without citation.',
    latency_ms: 900 * position,
    usage: { prompt_tokens: 100, completion_tokens: 50, total_tokens: 150 },
    estimated_cost_usd: null,
    tool_calling_supported: position === 1,
    data_disclosure: null,
    context_sha256: 'b'.repeat(64),
    scores: {
      accuracy: { score: 0.5, correct: 4, wrong: 0, not_mentioned: 4, wrong_numbers: {} },
      completeness: { score: 0.75 },
      relevance: { score: 1 },
      citation_correctness: { score: 1, no_citations: false },
      overall_demo_score: 0.81,
    },
    citation_check: CHECK_OK,
    ...overrides,
  };
}

export function comparisonRun(overrides: Partial<ComparisonRunResponse> = {}): ComparisonRunResponse {
  return {
    id: 'cmp-1',
    label: 'Demonstration comparison, not a formal benchmark.',
    scoring_note: 'Scores come from simple automated heuristics.',
    question: FIXED_QUESTION,
    status: 'completed',
    data_version_consistent: true,
    identical_context_verified: true,
    shared_context: {
      scenario_key: 'surge',
      scenario_name: 'Emergency Surge',
      data_version: 2,
      snapshot_metrics: { patients_waiting: 38, avg_wait_minutes: 75 },
      tools_executed: [
        { sequence: 1, tool_name: 'get_bed_availability', status: 'ok', arguments: {}, output: { available: 1 }, error: null, duration_ms: 9, data_version: 2 },
      ],
      retrieved_policies: [
        { document_name: 'Hospital Escalation Procedures', page: 2, score: 0.8, excerpt: 'Escalate at 60 minutes.', matched_query: 'wait', flagged: false },
      ],
      context_sha256: 'b'.repeat(64),
    },
    results: [modelResult(1), modelResult(2)],
    created_by: 'demo_presenter',
    created_at: '2026-11-22T10:05:00Z',
    ...overrides,
  };
}

export const COMPARISON_HISTORY: ComparisonHistoryPage = {
  items: [
    {
      id: 'cmp-0',
      label: 'Demonstration comparison, not a formal benchmark.',
      question: FIXED_QUESTION,
      status: 'completed',
      scenario_name: 'Normal Operations',
      data_version: 1,
      data_version_consistent: true,
      models: ['ollama/model-a', 'ollama/model-b'],
      created_at: '2026-11-22T09:00:00Z',
    },
  ],
  total: 1,
  limit: 10,
  offset: 0,
};
