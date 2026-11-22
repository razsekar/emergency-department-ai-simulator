import { ProviderName, Usage } from '../playground/providers.service';

/** Mirrors backend/app/modules/ai_orchestration/application/contracts.py. */
export type AgentMode = 'auto' | 'native' | 'fallback';

export interface AgentRunRequest {
  question: string;
  provider: ProviderName;
  model: string;
  temperature?: number | null;
  mode: AgentMode;
}

export interface ToolExecutionView {
  sequence: number;
  tool_name: string;
  status: string; // ok | invalid_arguments | unknown_tool | error | refused
  arguments: Record<string, unknown>;
  output: Record<string, unknown> | null;
  error: string | null;
  duration_ms: number;
  data_version: number | null;
}

export interface RetrievedPolicyView {
  document_name: string;
  page: number;
  score: number;
  excerpt: string;
  matched_query: string;
  flagged: boolean;
}

export interface CitationItem {
  document: string;
  page: number;
  verified: boolean;
}

/** Shape produced by backend domain/citations.py (check_citations). */
export interface CitationCheck {
  citations?: CitationItem[];
  verified_count?: number;
  unverified_count?: number;
  unverified?: CitationItem[];
  retrieved_count?: number;
}

export interface AgentRunResponse {
  id: string;
  run_type: 'agent' | 'demo';
  question: string;
  status: 'completed' | 'failed';
  error: string | null;
  answer: string | null;
  mode: 'native' | 'fallback';
  fallback_reason: string | null;
  scenario_key: string | null;
  scenario_name: string | null;
  data_version: number | null;
  data_version_consistent: boolean;
  snapshot_metrics: Record<string, unknown>;
  tools_executed: ToolExecutionView[];
  retrieved_policies: RetrievedPolicyView[];
  citation_check: CitationCheck;
  provider: string;
  model: string;
  temperature: number | null;
  llm_calls: number;
  latency_ms: number;
  usage: Usage;
  estimated_cost_usd: number | null;
  data_disclosure: string | null;
  created_by: string;
  created_at: string;
}

export interface RunSummary {
  id: string;
  run_type: string;
  question: string;
  scenario_name: string | null;
  data_version: number | null;
  provider: string;
  model: string;
  mode: string;
  status: string;
  tool_names: string[];
  latency_ms: number;
  total_tokens: number | null;
  created_at: string;
}

export interface RunPage {
  items: RunSummary[];
  total: number;
  limit: number;
  offset: number;
}

export type RunTypeFilter = 'all' | 'agent' | 'demo';
