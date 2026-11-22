import { AgentRunResponse, RunPage } from '../agent/agent.models';
import { ModelInfo, ProviderStatus } from '../playground/providers.service';

export const STATUSES: ProviderStatus[] = [
  { provider: 'ollama', label: 'Ollama (local)', configured: true, reachable: true, cloud: false, data_disclosure: null, detail: 'reachable' },
  { provider: 'openai', label: 'OpenAI', configured: false, reachable: null, cloud: true, data_disclosure: 'Prompts are sent to OpenAI.', detail: 'Set OPENAI_API_KEY' },
];

export const MODELS: ModelInfo[] = [
  { provider: 'ollama', model_id: 'qwen3:8b', display_name: 'qwen3:8b', source: 'discovered', supports_tools: true, cloud: false },
];

export const DEMO_QUESTION = 'Analyze the current emergency department situation. Identify operational bottlenecks.';

export function runResponse(overrides: Partial<AgentRunResponse> = {}): AgentRunResponse {
  return {
    id: 'run-1',
    run_type: 'agent',
    question: DEMO_QUESTION,
    status: 'completed',
    error: null,
    answer:
      'Waiting patients are far above the normal level at 38 [Source: Hospital Escalation Procedures, p.2].\n\n' +
      'In general, longer queues tend to raise walk-out risk.\n\n' +
      'Open an extra bay [Source: Invented Policy, p.9].',
    mode: 'native',
    fallback_reason: null,
    scenario_key: 'surge',
    scenario_name: 'Emergency Surge',
    data_version: 2,
    data_version_consistent: true,
    snapshot_metrics: { patients_waiting: 38, avg_wait_minutes: 75, bed_utilization_pct: 91.7 },
    tools_executed: [
      { sequence: 1, tool_name: 'get_bed_availability', status: 'ok', arguments: {}, output: { available: 1 }, error: null, duration_ms: 12, data_version: 2 },
      { sequence: 2, tool_name: 'get_patient_queue', status: 'invalid_arguments', arguments: { status: 'bogus' }, output: null, error: 'status: not a valid status', duration_ms: 3, data_version: null },
    ],
    retrieved_policies: [
      { document_name: 'Hospital Escalation Procedures', page: 2, score: 0.8123, excerpt: 'Escalate when average wait exceeds 60 minutes.', matched_query: 'wait over 60', flagged: false },
      { document_name: 'Resource Management Guidelines', page: 1, score: 0.5, excerpt: '[withheld: possible prompt injection in source text]', matched_query: 'beds', flagged: true },
    ],
    citation_check: {
      citations: [
        { document: 'Hospital Escalation Procedures', page: 2, verified: true },
        { document: 'Invented Policy', page: 9, verified: false },
      ],
      verified_count: 1,
      unverified_count: 1,
      unverified: [{ document: 'Invented Policy', page: 9, verified: false }],
      retrieved_count: 2,
    },
    provider: 'ollama',
    model: 'qwen3:8b',
    temperature: 0.2,
    llm_calls: 3,
    latency_ms: 4200,
    usage: { prompt_tokens: 1000, completion_tokens: 200, total_tokens: 1200 },
    estimated_cost_usd: null,
    data_disclosure: null,
    created_by: 'demo_presenter',
    created_at: '2026-11-22T09:00:00Z',
    ...overrides,
  };
}

export const RUN_PAGE: RunPage = {
  items: [
    {
      id: 'run-1', run_type: 'agent', question: DEMO_QUESTION, scenario_name: 'Emergency Surge', data_version: 2,
      provider: 'ollama', model: 'qwen3:8b', mode: 'native', status: 'completed',
      tool_names: ['get_bed_availability', 'get_patient_queue'], latency_ms: 4200, total_tokens: 1200, created_at: '2026-11-22T09:00:00Z',
    },
  ],
  total: 21,
  limit: 10,
  offset: 0,
};
