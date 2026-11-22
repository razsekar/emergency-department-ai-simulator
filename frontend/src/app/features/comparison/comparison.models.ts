import { CitationCheck, RetrievedPolicyView, ToolExecutionView } from '../agent/agent.models';
import { ProviderName, Usage } from '../playground/providers.service';

/** Mirrors backend/app/modules/ai_orchestration/application/comparison_contracts.py. */
export const COMPARISON_MIN_MODELS = 2;
export const COMPARISON_MAX_MODELS = 6;
export const DEMO_LABEL = 'Demonstration comparison, not a formal benchmark.';

export interface ModelSelection {
  provider: ProviderName;
  model: string;
  temperature?: number | null;
}

export interface ComparisonRunRequest {
  /** Omitted so the backend uses its fixed demonstration question. */
  question?: string;
  selections: ModelSelection[];
}

export interface SharedContextView {
  scenario_key: string | null;
  scenario_name: string | null;
  data_version: number | null;
  snapshot_metrics: Record<string, unknown>;
  tools_executed: ToolExecutionView[];
  retrieved_policies: RetrievedPolicyView[];
  context_sha256: string;
}

/** Shapes produced by backend domain/comparison_scoring.py (score_answer). All scores are fractions or null. */
export interface AccuracyDetail {
  score: number | null;
  correct?: number;
  wrong?: number;
  not_mentioned?: number;
  /** metric name -> numbers the answer stated that differ from the true snapshot value. */
  wrong_numbers?: Record<string, number[]>;
}

export interface ScoreBlock {
  score: number | null;
  missing?: string[];
  out_of_scope_terms?: string[];
  no_citations?: boolean;
}

export interface ComparisonScores {
  accuracy?: AccuracyDetail;
  completeness?: ScoreBlock;
  relevance?: ScoreBlock;
  citation_correctness?: ScoreBlock;
  overall_demo_score?: number | null;
  note?: string;
}

export interface ModelResultView {
  position: number;
  provider: string;
  model: string;
  temperature: number | null;
  status: 'completed' | 'failed' | 'not_configured';
  error: string | null;
  answer: string | null;
  latency_ms: number | null;
  usage: Usage;
  estimated_cost_usd: number | null;
  tool_calling_supported: boolean | null;
  data_disclosure: string | null;
  context_sha256: string | null;
  scores: ComparisonScores;
  citation_check: CitationCheck;
}

export interface ComparisonRunResponse {
  id: string;
  label: string;
  scoring_note: string;
  question: string;
  status: 'completed' | 'partial' | 'failed';
  data_version_consistent: boolean;
  identical_context_verified: boolean;
  shared_context: SharedContextView;
  results: ModelResultView[];
  created_by: string;
  created_at: string;
}

export interface ComparisonSummary {
  id: string;
  label: string;
  question: string;
  status: string;
  scenario_name: string | null;
  data_version: number | null;
  data_version_consistent: boolean;
  models: string[];
  created_at: string;
}

export interface ComparisonHistoryPage {
  items: ComparisonSummary[];
  total: number;
  limit: number;
  offset: number;
}
