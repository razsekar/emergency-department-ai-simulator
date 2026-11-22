import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ComparisonHistoryPage, ComparisonRunRequest, ComparisonRunResponse } from './comparison.models';

/** Typed client for /api/comparison (ai_orchestration). Scoring and context sharing happen in the backend. */
@Injectable({ providedIn: 'root' })
export class ComparisonService {
  private readonly http = inject(HttpClient);

  run(request: ComparisonRunRequest): Observable<ComparisonRunResponse> {
    return this.http.post<ComparisonRunResponse>('/api/comparison/run', request);
  }

  runs(limit: number, offset: number): Observable<ComparisonHistoryPage> {
    const params = new HttpParams().set('limit', limit).set('offset', offset);
    return this.http.get<ComparisonHistoryPage>('/api/comparison/runs', { params });
  }

  detail(id: string): Observable<ComparisonRunResponse> {
    return this.http.get<ComparisonRunResponse>(`/api/comparison/runs/${encodeURIComponent(id)}`);
  }
}
