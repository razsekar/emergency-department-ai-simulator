import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthService } from '../../core/auth/auth.service';
import { ChatStreamService, StreamHttpError, parseSseBuffer } from './chat-stream.service';
import { StreamEvent, formatCost, formatTokens } from './providers.service';

const frame = (e: StreamEvent) => `event: ${e.type}\ndata: ${JSON.stringify(e)}\n\n`;

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(c) {
      chunks.forEach((x) => c.enqueue(enc.encode(x)));
      c.close();
    },
  });
}

describe('parseSseBuffer', () => {
  it('returns complete events and keeps a partial frame as the remainder', () => {
    const text = frame({ type: 'start' }) + frame({ type: 'delta', content: 'Hi' }) + 'event: delta\ndata: {"ty';
    const { events, rest } = parseSseBuffer(text);
    expect(events.map((e) => e.type)).toEqual(['start', 'delta']);
    expect(events[1].content).toBe('Hi');
    expect(rest).toBe('event: delta\ndata: {"ty');
  });

  it('reports malformed JSON as an error event instead of throwing', () => {
    const { events } = parseSseBuffer('event: delta\ndata: {nope\n\n');
    expect(events).toEqual([{ type: 'error', message: 'Received a malformed stream event.' }]);
  });
});

describe('ChatStreamService', () => {
  const request = { provider: 'ollama' as const, model: 'm', messages: [{ role: 'user' as const, content: 'hi' }] };

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
  });
  afterEach(() => vi.unstubAllGlobals());

  it('streams events split across chunk boundaries and sends the bearer token', async () => {
    const auth = TestBed.inject(AuthService);
    vi.spyOn(auth, 'token').mockReturnValue('abc');
    const full = frame({ type: 'start' }) + frame({ type: 'delta', content: 'Hel' }) + frame({ type: 'delta', content: 'lo' });
    const mid = Math.floor(full.length / 2);
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, body: streamOf([full.slice(0, mid), full.slice(mid)]) });
    vi.stubGlobal('fetch', fetchMock);

    const seen: StreamEvent[] = [];
    await TestBed.inject(ChatStreamService).stream(request, (e) => seen.push(e));

    expect(seen.filter((e) => e.type === 'delta').map((e) => e.content).join('')).toBe('Hello');
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)['Authorization']).toBe('Bearer abc');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/providers/chat/stream');
  });

  it('turns a 409 not-configured response into a helpful error', async () => {
    const body = { error: { code: 'provider_not_configured', message: 'Set ANTHROPIC_API_KEY to use Anthropic.' } };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 409, json: async () => body }));
    const err = await TestBed.inject(ChatStreamService)
      .stream(request, () => undefined)
      .catch((e: unknown) => e);
    expect(err).toBeInstanceOf(StreamHttpError);
    expect((err as StreamHttpError).status).toBe(409);
    expect((err as StreamHttpError).message).toBe('Set ANTHROPIC_API_KEY to use Anthropic.');
  });

  it('signs the user out on a 401', async () => {
    const auth = TestBed.inject(AuthService);
    const logout = vi.spyOn(auth, 'logout');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({}) }));
    await TestBed.inject(ChatStreamService)
      .stream(request, () => undefined)
      .catch(() => undefined);
    expect(logout).toHaveBeenCalled();
  });
});

describe('formatters', () => {
  it('shows "not available" instead of inventing cost or tokens', () => {
    expect(formatCost(null)).toBe('not available');
    expect(formatTokens(null)).toBe('not available');
    expect(formatTokens({ prompt_tokens: null, completion_tokens: null, total_tokens: null })).toBe('not available');
  });
  it('formats real values', () => {
    expect(formatCost(0.00123)).toBe('$0.00123');
    expect(formatCost(0.5)).toBe('$0.500');
    expect(formatTokens({ prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 })).toBe('10 in / 5 out (15 total)');
  });
});
