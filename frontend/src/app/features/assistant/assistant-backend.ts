import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { CitationCheck, RetrievedPolicyView } from '../agent/agent.models';
import { ChatStreamService } from '../playground/chat-stream.service';
import { ChatMessage, ModelInfo, Usage } from '../playground/providers.service';

export interface AssistantTurn {
  model: ModelInfo;
  temperature: number | null;
  /** The new user message. Server-side sessions only need this. */
  content: string;
  /** Whole transcript including the new message, for backends that are stateless (provider chat). */
  history: ChatMessage[];
  streaming: boolean;
}

/** Facts about a finished assistant reply, independent of which backend produced it. */
export interface TurnMeta {
  provider: string;
  model: string;
  latency_ms: number | null;
  usage: Usage | null;
  estimated_cost_usd: number | null;
  sources: RetrievedPolicyView[];
  citation_check: CitationCheck | null;
  data_disclosure: string | null;
}

export type AssistantEvent =
  | { type: 'sources'; sources: RetrievedPolicyView[] }
  | { type: 'delta'; content: string }
  | { type: 'done'; meta: TurnMeta }
  | { type: 'error'; message: string };

/**
 * Seam for the AI Assistant: the page only knows this interface. `RagChatBackend` (used) answers from
 * retrieved policy plus a live-data snapshot with citations; `ProviderChatBackend` is the plain model chat.
 */
export abstract class AssistantBackend {
  /** True when answers are grounded in retrieved policy documents with citations. */
  abstract readonly grounded: boolean;
  abstract send(turn: AssistantTurn, onEvent: (e: AssistantEvent) => void, signal?: AbortSignal): Promise<void>;
  /** Forget any server-side conversation so the next message starts a new one. */
  abstract reset(): void;
}

@Injectable({ providedIn: 'root' })
export class ProviderChatBackend extends AssistantBackend {
  private readonly stream = inject(ChatStreamService);
  readonly grounded = false;

  reset(): void {
    /* stateless: the page sends the whole history each time */
  }

  send(turn: AssistantTurn, onEvent: (e: AssistantEvent) => void, signal?: AbortSignal): Promise<void> {
    return this.stream.stream(
      { provider: turn.model.provider, model: turn.model.model_id, temperature: turn.temperature, messages: turn.history },
      (e) => {
        if (e.type === 'delta' && e.content) onEvent({ type: 'delta', content: e.content });
        else if (e.type === 'done' && e.response) {
          const r = e.response;
          onEvent({
            type: 'done',
            meta: {
              provider: r.provider,
              model: r.model,
              latency_ms: r.latency_ms,
              usage: r.usage,
              estimated_cost_usd: r.estimated_cost_usd,
              sources: [],
              citation_check: null,
              data_disclosure: r.data_disclosure,
            },
          });
        } else if (e.type === 'error') onEvent({ type: 'error', message: e.message ?? 'The provider reported an error.' });
      },
      signal,
    );
  }
}

// ---- RAG chat (backend: ai_orchestration/api/router.py, contracts.py) ----
export interface RagChatMessageView {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources: RetrievedPolicyView[];
  citation_check: CitationCheck;
  provider: string | null;
  model: string | null;
  latency_ms: number | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  data_disclosure: string | null;
  created_at: string;
}

export interface RagSendResponse {
  user_message: RagChatMessageView;
  assistant_message: RagChatMessageView;
  usage: Usage;
  estimated_cost_usd: number | null;
}

/** Events of POST /api/chat/sessions/{id}/messages/stream (see ChatService.stream_events). */
export type RagStreamEvent =
  | { type: 'sources'; sources: RetrievedPolicyView[]; user_message: RagChatMessageView }
  | { type: 'delta'; content: string }
  | { type: 'done'; assistant_message: RagChatMessageView; usage: Usage | null; estimated_cost_usd: number | null }
  | { type: 'error'; message: string };

export function metaFromAssistantMessage(m: RagChatMessageView, usage: Usage | null, cost: number | null): TurnMeta {
  const total =
    usage ??
    (m.prompt_tokens !== null || m.completion_tokens !== null
      ? { prompt_tokens: m.prompt_tokens, completion_tokens: m.completion_tokens, total_tokens: (m.prompt_tokens ?? 0) + (m.completion_tokens ?? 0) }
      : null);
  return {
    provider: m.provider ?? 'unknown',
    model: m.model ?? 'unknown',
    latency_ms: m.latency_ms,
    usage: total,
    estimated_cost_usd: cost,
    sources: m.sources ?? [],
    citation_check: m.citation_check ?? null,
    data_disclosure: m.data_disclosure,
  };
}

@Injectable({ providedIn: 'root' })
export class RagChatBackend extends AssistantBackend {
  private readonly http = inject(HttpClient);
  private readonly stream = inject(ChatStreamService);
  readonly grounded = true;
  private sessionId: string | null = null;

  reset(): void {
    this.sessionId = null;
  }

  async send(turn: AssistantTurn, onEvent: (e: AssistantEvent) => void, signal?: AbortSignal): Promise<void> {
    const id = await this.ensureSession(turn.content);
    const url = `/api/chat/sessions/${encodeURIComponent(id)}/messages`;
    const body = {
      content: turn.content,
      provider: turn.model.provider,
      model: turn.model.model_id,
      temperature: turn.temperature,
      use_rag: true,
      include_live_data: true,
    };

    if (!turn.streaming) {
      const res = await firstValueFrom(this.http.post<RagSendResponse>(url, body));
      onEvent({ type: 'sources', sources: res.assistant_message.sources ?? [] });
      onEvent({ type: 'delta', content: res.assistant_message.content });
      onEvent({ type: 'done', meta: metaFromAssistantMessage(res.assistant_message, res.usage, res.estimated_cost_usd) });
      return;
    }

    await this.stream.postStream<RagStreamEvent>(
      `${url}/stream`,
      body,
      (e) => {
        if (e.type === 'sources') onEvent({ type: 'sources', sources: e.sources ?? [] });
        else if (e.type === 'delta') onEvent({ type: 'delta', content: e.content });
        else if (e.type === 'done') {
          onEvent({ type: 'done', meta: metaFromAssistantMessage(e.assistant_message, e.usage, e.estimated_cost_usd) });
        } else if (e.type === 'error') onEvent({ type: 'error', message: e.message });
      },
      signal,
    );
  }

  private async ensureSession(firstMessage: string): Promise<string> {
    if (this.sessionId) return this.sessionId;
    const title = firstMessage.trim().slice(0, 60) || 'New conversation';
    const created = await firstValueFrom(this.http.post<{ id: string }>('/api/chat/sessions', { title }));
    this.sessionId = created.id;
    return created.id;
  }
}
