import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';
import {
  ApplyResponse,
  DataState,
  RunPage,
  ScenarioInfo,
  ScenarioKey,
  ScenarioOverrides,
} from './simulator.models';

/** Extracts a human-readable message from the backend's error shapes (app errors and FastAPI 422s). */
export function apiErrorMessage(err: unknown): string {
  if (err instanceof HttpErrorResponse) {
    const body = err.error as
      | { error?: { message?: string }; detail?: string | { msg?: string }[] }
      | null;
    if (body?.error?.message) return body.error.message;
    if (typeof body?.detail === 'string') return body.detail;
    if (Array.isArray(body?.detail)) return body.detail.map((d) => d.msg ?? '').join('; ');
    if (err.status === 0) return 'Backend is unreachable.';
    return `Request failed (HTTP ${err.status}).`;
  }
  return 'Unexpected error.';
}

/**
 * Typed client for /api/scenarios AND the single source of truth for the current scenario/data version.
 * Other features read `dataVersion()` to refresh themselves after a scenario is applied.
 */
@Injectable({ providedIn: 'root' })
export class ScenarioService {
  private readonly http = inject(HttpClient);

  private readonly _state = signal<DataState | null>(null);
  readonly state = this._state.asReadonly();
  /** Null until the first state has been loaded. */
  readonly dataVersion = computed(() => this._state()?.data_version ?? null);

  list(): Observable<ScenarioInfo[]> {
    return this.http.get<ScenarioInfo[]>('/api/scenarios');
  }

  history(limit = 20, offset = 0): Observable<RunPage> {
    return this.http.get<RunPage>('/api/scenarios/history', { params: { limit, offset } });
  }

  /** Loads the current scenario name and data version from the backend. */
  refreshState(): Observable<DataState> {
    return this.http.get<DataState>('/api/scenarios/current').pipe(tap((s) => this._state.set(s)));
  }

  apply(key: ScenarioKey, overrides?: ScenarioOverrides): Observable<ApplyResponse> {
    const body = overrides ? { scenario_key: key, overrides } : { scenario_key: key };
    return this.http.post<ApplyResponse>('/api/scenarios/apply', body).pipe(this.adopt());
  }

  randomize(): Observable<ApplyResponse> {
    return this.http.post<ApplyResponse>('/api/scenarios/randomize', {}).pipe(this.adopt());
  }

  reset(): Observable<ApplyResponse> {
    return this.http.post<ApplyResponse>('/api/scenarios/reset', {}).pipe(this.adopt());
  }

  /** The new state comes from the server response, never from local guesses. */
  private adopt() {
    return tap<ApplyResponse>((r) => this._state.set(r.state));
  }
}
