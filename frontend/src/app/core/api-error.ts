import { HttpErrorResponse } from '@angular/common/http';

/** Backend error envelope: {"error": {"code": "...", "message": "..."}} */
interface ErrorEnvelope {
  error?: { code?: string; message?: string };
  detail?: unknown;
}

export function messageFromBody(status: number, body: unknown): string {
  const env = (body ?? {}) as ErrorEnvelope;
  const msg = env.error?.message;
  if (status === 409 && msg) return msg; // e.g. provider not configured: names the env var to set
  if (status === 401) return 'Your session has expired or you are not signed in.';
  if (status === 403) return 'Your role does not permit this action.';
  if (status === 413) return 'The file is too large.';
  if (status === 422) return msg ?? 'The request was rejected as invalid.';
  if (msg) return msg;
  if (status === 0) return 'Cannot reach the backend.';
  return `Request failed (HTTP ${status}).`;
}

export function describeApiError(err: unknown): string {
  if (err instanceof HttpErrorResponse) return messageFromBody(err.status, err.error);
  if (err instanceof Error) return err.message;
  return 'Unexpected error.';
}
