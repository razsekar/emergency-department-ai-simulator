import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';
import { DemoResetResponse, DemoSessionView, DemoStepRequest, DemoStepResponse } from './demo.models';

/** Typed client for /api/demo (ai_orchestration). All verification logic stays in the backend. */
@Injectable({ providedIn: 'root' })
export class DemoService {
  private readonly http = inject(HttpClient);

  /** The fixed demonstration question, read from the backend so it is byte-identical everywhere. */
  question(): Observable<string> {
    return this.http.get<{ question: string }>('/api/demo/question').pipe(map((r) => r.question));
  }

  /** Applies the scenario in the database, verifies the data changed, asks the fixed question, saves the run. */
  step(request: DemoStepRequest): Observable<DemoStepResponse> {
    return this.http.post<DemoStepResponse>('/api/demo/step', request);
  }

  session(): Observable<DemoSessionView> {
    return this.http.get<DemoSessionView>('/api/demo/session');
  }

  /** Clears saved demo runs and reloads the Normal baseline so the demo can be replayed. */
  reset(): Observable<DemoResetResponse> {
    return this.http.post<DemoResetResponse>('/api/demo/session/reset', {});
  }
}
