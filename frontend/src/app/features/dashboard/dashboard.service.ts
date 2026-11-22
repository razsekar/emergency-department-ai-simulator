import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { DashboardMetrics, ResourceUtilization } from './dashboard.models';

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly http = inject(HttpClient);

  /** Metrics are calculated by the backend from database records on every call (never cached here). */
  metrics(windowMinutes = 240, bucketMinutes = 30): Observable<DashboardMetrics> {
    return this.http.get<DashboardMetrics>('/api/dashboard/metrics', {
      params: { window_minutes: windowMinutes, bucket_minutes: bucketMinutes },
    });
  }

  resourceUtilization(): Observable<ResourceUtilization> {
    return this.http.get<ResourceUtilization>('/api/dashboard/resource-utilization');
  }
}

/** Picks a bucket size (5–120 min, multiples of 5) that gives roughly 8 bars for the chosen window. */
export function bucketForWindow(windowMinutes: number): number {
  const raw = Math.round(windowMinutes / 8 / 5) * 5;
  return Math.min(120, Math.max(5, raw));
}
