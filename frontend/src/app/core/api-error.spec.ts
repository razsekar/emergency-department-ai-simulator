import { HttpErrorResponse } from '@angular/common/http';
import { describe, expect, it } from 'vitest';
import { describeApiError, messageFromBody } from './api-error';

describe('api error messages', () => {
  it('surfaces the server message for 409 (provider not configured)', () => {
    expect(messageFromBody(409, { error: { code: 'x', message: 'Set OPENAI_API_KEY.' } })).toBe('Set OPENAI_API_KEY.');
  });
  it('gives clear messages for 401/403/0', () => {
    expect(messageFromBody(401, null)).toMatch(/session/);
    expect(messageFromBody(403, null)).toMatch(/role/);
    expect(messageFromBody(0, null)).toMatch(/reach/);
  });
  it('handles HttpErrorResponse and unknown errors', () => {
    expect(describeApiError(new HttpErrorResponse({ status: 500, error: {} }))).toMatch(/HTTP 500/);
    expect(describeApiError('weird')).toBe('Unexpected error.');
  });
});
