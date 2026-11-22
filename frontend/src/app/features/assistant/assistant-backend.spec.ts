import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MODELS } from '../testing/agent-fixtures';
import { AssistantEvent, AssistantTurn, RagChatBackend, RagChatMessageView, RagSendResponse } from './assistant-backend';

const SOURCE = { document_name: 'Hospital Escalation Procedures', page: 2, score: 0.81, excerpt: 'Escalate above 60 min.', matched_query: 'q', flagged: false };

const reply = (over: Partial<RagChatMessageView> = {}): RagChatMessageView => ({
  id: 'm2', role: 'assistant', content: 'Escalate [Source: Hospital Escalation Procedures, p.2].', sources: [SOURCE],
  citation_check: { citations: [{ document: 'Hospital Escalation Procedures', page: 2, verified: true }], verified_count: 1, unverified_count: 0, retrieved_count: 1 },
  provider: 'ollama', model: 'qwen3:8b', latency_ms: 900, prompt_tokens: 100, completion_tokens: 20, data_disclosure: null,
  created_at: '2026-11-22T09:00:00Z', ...over,
});

const frame = (type: string, payload: object) => `event: ${type}\ndata: ${JSON.stringify({ type, ...payload })}\n\n`;

function streamOf(text: string): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(c) {
      c.enqueue(enc.encode(text));
      c.close();
    },
  });
}

const turn = (over: Partial<AssistantTurn> = {}): AssistantTurn => ({
  model: MODELS[0], temperature: 0.2, content: 'What is the escalation rule?', history: [], streaming: true, ...over,
});

describe('RagChatBackend', () => {
  let http: HttpTestingController;
  let backend: RagChatBackend;

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    backend = TestBed.inject(RagChatBackend);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    http.verify();
  });

  it('is the grounded (cited) backend', () => {
    expect(backend.grounded).toBe(true);
  });

  it('creates a session once, streams sources then deltas then done with citation metadata', async () => {
    const body =
      frame('sources', { sources: [SOURCE], user_message: reply({ role: 'user' }) }) +
      frame('delta', { content: 'Escalate ' }) +
      frame('delta', { content: '[Source: Hospital Escalation Procedures, p.2].' }) +
      frame('done', { assistant_message: reply(), usage: { prompt_tokens: 100, completion_tokens: 20, total_tokens: 120 }, estimated_cost_usd: null });
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, body: streamOf(body) });
    vi.stubGlobal('fetch', fetchMock);

    const events: AssistantEvent[] = [];
    const p = backend.send(turn(), (e) => events.push(e));
    const created = http.expectOne('/api/chat/sessions');
    expect(created.request.body).toEqual({ title: 'What is the escalation rule?' });
    created.flush({ id: 's1' });
    await p;

    expect(fetchMock.mock.calls[0][0]).toBe('/api/chat/sessions/s1/messages/stream');
    const sent = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string);
    expect(sent).toMatchObject({ content: 'What is the escalation rule?', provider: 'ollama', model: 'qwen3:8b', use_rag: true, include_live_data: true });

    expect(events.map((e) => e.type)).toEqual(['sources', 'delta', 'delta', 'done']);
    const done = events[3];
    expect(done.type === 'done' && done.meta.sources[0].document_name).toBe('Hospital Escalation Procedures');
    expect(done.type === 'done' && done.meta.citation_check?.verified_count).toBe(1);
    expect(done.type === 'done' && done.meta.usage?.total_tokens).toBe(120);
    expect(done.type === 'done' && done.meta.estimated_cost_usd).toBeNull();

    // second message reuses the session (no new POST /sessions)
    fetchMock.mockResolvedValue({ ok: true, status: 200, body: streamOf(frame('done', { assistant_message: reply(), usage: null, estimated_cost_usd: null })) });
    await backend.send(turn(), () => undefined);
    expect(fetchMock.mock.calls[1][0]).toBe('/api/chat/sessions/s1/messages/stream');
  });

  it('reset() makes the next message start a new conversation', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(async () => ({ ok: true, status: 200, body: streamOf(frame('done', { assistant_message: reply(), usage: null, estimated_cost_usd: null })) })));
    let p = backend.send(turn(), () => undefined);
    http.expectOne('/api/chat/sessions').flush({ id: 's1' });
    await p;
    backend.reset();
    p = backend.send(turn(), () => undefined);
    http.expectOne('/api/chat/sessions').flush({ id: 's2' });
    await p;
  });

  it('uses the non-streaming endpoint when streaming is off and still reports sources and meta', async () => {
    const events: AssistantEvent[] = [];
    const p = backend.send(turn({ streaming: false }), (e) => events.push(e));
    http.expectOne('/api/chat/sessions').flush({ id: 's1' });
    const req = await vi.waitFor(() => http.expectOne('/api/chat/sessions/s1/messages'));
    const res: RagSendResponse = { user_message: reply({ role: 'user' }), assistant_message: reply(), usage: { prompt_tokens: 1, completion_tokens: 2, total_tokens: 3 }, estimated_cost_usd: 0.001 };
    req.flush(res);
    await p;
    expect(events.map((e) => e.type)).toEqual(['sources', 'delta', 'done']);
    const done = events[2];
    expect(done.type === 'done' && done.meta.estimated_cost_usd).toBe(0.001);
  });

  it('surfaces a stream error event', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, body: streamOf(frame('error', { message: 'The provider stream failed.' })) }));
    const events: AssistantEvent[] = [];
    const p = backend.send(turn(), (e) => events.push(e));
    http.expectOne('/api/chat/sessions').flush({ id: 's1' });
    await p;
    expect(events).toEqual([{ type: 'error', message: 'The provider stream failed.' }]);
  });

  it('turns a 409 not-configured response into a helpful error', async () => {
    const msg = { error: { code: 'provider_not_configured', message: 'Set OPENAI_API_KEY to use OpenAI.' } };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 409, json: async () => msg }));
    const p = backend.send(turn(), () => undefined).catch((e: unknown) => e);
    http.expectOne('/api/chat/sessions').flush({ id: 's1' });
    expect(((await p) as Error).message).toBe('Set OPENAI_API_KEY to use OpenAI.');
  });
});
