import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

/** Mirrors backend/app/modules/model_providers/application/contracts.py. No secrets ever appear here. */
export type ProviderName = 'anthropic' | 'openai' | 'gemini' | 'ollama';

export interface ProviderStatus {
  provider: ProviderName;
  label: string;
  configured: boolean;
  reachable: boolean | null;
  cloud: boolean;
  data_disclosure: string | null;
  detail: string;
}

export interface ModelInfo {
  provider: ProviderName;
  model_id: string;
  display_name: string;
  source: 'env' | 'database' | 'discovered';
  supports_tools: boolean | null;
  cloud: boolean;
}

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string | null;
}

export interface ChatRequest {
  provider: ProviderName;
  model: string;
  messages: ChatMessage[];
  temperature?: number | null;
  max_tokens?: number | null;
}

export interface Usage {
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
}

export interface ChatResponse {
  provider: ProviderName;
  model: string;
  content: string | null;
  finish_reason: string | null;
  usage: Usage;
  estimated_cost_usd: number | null;
  latency_ms: number;
  tool_calling_supported: boolean | null;
  cloud: boolean;
  data_disclosure: string | null;
  temperature_applied: boolean;
}

export interface StreamEvent {
  type: 'start' | 'delta' | 'done' | 'error';
  content?: string | null;
  response?: ChatResponse | null;
  message?: string | null;
}

@Injectable({ providedIn: 'root' })
export class ProvidersService {
  private readonly http = inject(HttpClient);

  status(probe = false): Observable<ProviderStatus[]> {
    const params = new HttpParams().set('probe', probe);
    return this.http.get<ProviderStatus[]>('/api/providers/status', { params });
  }

  models(): Observable<ModelInfo[]> {
    return this.http.get<ModelInfo[]>('/api/providers/models');
  }

  chat(request: ChatRequest): Observable<ChatResponse> {
    return this.http.post<ChatResponse>('/api/providers/chat', request);
  }
}

export function formatCost(usd: number | null | undefined): string {
  if (usd === null || usd === undefined) return 'not available';
  return usd < 0.01 ? `$${usd.toFixed(5)}` : `$${usd.toFixed(3)}`;
}

export function formatTokens(usage: Usage | null | undefined): string {
  if (!usage || usage.total_tokens === null) return 'not available';
  return `${usage.prompt_tokens ?? '?'} in / ${usage.completion_tokens ?? '?'} out (${usage.total_tokens} total)`;
}
