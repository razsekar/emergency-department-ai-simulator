import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';
import { AgentRunRequest, AgentRunResponse, RunPage, RunTypeFilter } from './agent.models';

/** Typed client for the agent endpoints in ai_orchestration (all business logic stays in the backend). */
@Injectable({ providedIn: 'root' })
export class AgentService {
  private readonly http = inject(HttpClient);

  /** The fixed demonstration question lives in the backend so it is identical everywhere. */
  demoQuestion(): Observable<string> {
    return this.http.get<{ question: string }>('/api/agent/demo-question').pipe(map((r) => r.question));
  }

  run(request: AgentRunRequest): Observable<AgentRunResponse> {
    return this.http.post<AgentRunResponse>('/api/agent/run', request);
  }

  runs(limit: number, offset: number, runType: RunTypeFilter = 'all'): Observable<RunPage> {
    let params = new HttpParams().set('limit', limit).set('offset', offset);
    if (runType !== 'all') params = params.set('run_type', runType);
    return this.http.get<RunPage>('/api/agent/runs', { params });
  }

  runDetail(id: string): Observable<AgentRunResponse> {
    return this.http.get<AgentRunResponse>(`/api/agent/runs/${encodeURIComponent(id)}`);
  }
}
