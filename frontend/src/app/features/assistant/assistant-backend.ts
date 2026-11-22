import { Injectable, inject } from '@angular/core';
import { ChatStreamService } from '../playground/chat-stream.service';
import { ChatMessage, ModelInfo, StreamEvent } from '../playground/providers.service';

export interface AssistantTurn {
  model: ModelInfo;
  temperature: number | null;
  history: ChatMessage[];
}

/**
 * Seam for the AI Assistant. Today it talks to the generic provider chat endpoint (no retrieval).
 * When the RAG-grounded chat endpoint exists, provide another implementation with the same
 * shape (it should also return citations) and switch the factory below.
 */
export abstract class AssistantBackend {
  /** True when answers are grounded in retrieved policy documents with citations. */
  abstract readonly grounded: boolean;
  abstract send(turn: AssistantTurn, onEvent: (e: StreamEvent) => void, signal?: AbortSignal): Promise<void>;
}

@Injectable({ providedIn: 'root' })
export class ProviderChatBackend extends AssistantBackend {
  private readonly stream = inject(ChatStreamService);
  readonly grounded = false;

  send(turn: AssistantTurn, onEvent: (e: StreamEvent) => void, signal?: AbortSignal): Promise<void> {
    return this.stream.stream(
      {
        provider: turn.model.provider,
        model: turn.model.model_id,
        temperature: turn.temperature,
        messages: turn.history,
      },
      onEvent,
      signal,
    );
  }
}
