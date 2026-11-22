import { Injectable, inject } from '@angular/core';
import { AuthService } from '../../core/auth/auth.service';
import { messageFromBody } from '../../core/api-error';
import { ChatRequest, StreamEvent } from './providers.service';

export class StreamHttpError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

/**
 * Parses a Server-Sent Events text buffer. Returns the complete events plus the unconsumed remainder.
 * Frames look like: "event: delta\ndata: {json}\n\n" (see model_providers/api/router.py).
 */
export function parseSseBuffer<T = StreamEvent>(buffer: string): { events: T[]; rest: string } {
  const events: T[] = [];
  const frames = buffer.split('\n\n');
  const rest = frames.pop() ?? '';
  for (const frame of frames) {
    const data = frame
      .split('\n')
      .filter((l) => l.startsWith('data:'))
      .map((l) => l.slice(5).trimStart())
      .join('\n');
    if (!data) continue;
    try {
      events.push(JSON.parse(data) as T);
    } catch {
      events.push({ type: 'error', message: 'Received a malformed stream event.' } as T);
    }
  }
  return { events, rest };
}

/**
 * EventSource cannot send an Authorization header and only supports GET, so the stream is read
 * with fetch + ReadableStream instead.
 */
@Injectable({ providedIn: 'root' })
export class ChatStreamService {
  private readonly auth = inject(AuthService);

  /** Provider-level chat stream (the Model Playground). */
  stream(request: ChatRequest, onEvent: (e: StreamEvent) => void, signal?: AbortSignal): Promise<void> {
    return this.postStream<StreamEvent>('/api/providers/chat/stream', request, onEvent, signal);
  }

  /** POSTs JSON and reads the Server-Sent Events reply, delivering each parsed event to `onEvent`. */
  async postStream<T>(url: string, body: unknown, onEvent: (e: T) => void, signal?: AbortSignal): Promise<void> {
    const token = this.auth.token();
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
      signal,
    });

    if (!response.ok) {
      let body: unknown = null;
      try {
        body = await response.json();
      } catch {
        /* non-JSON error body */
      }
      if (response.status === 401) this.auth.logout();
      throw new StreamHttpError(response.status, messageFromBody(response.status, body));
    }
    if (!response.body) throw new StreamHttpError(0, 'The browser did not provide a readable stream.');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parsed = parseSseBuffer<T>(buffer);
      buffer = parsed.rest;
      parsed.events.forEach(onEvent);
    }
    buffer += decoder.decode();
    parseSseBuffer<T>(buffer + '\n\n').events.forEach(onEvent);
  }
}
