import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { toParams } from '../resources/resources.service';
import { PendingInvestigations, QueuePage, QueueQuery, WaitingMetrics } from './queue.models';

@Injectable({ providedIn: 'root' })
export class QueueService {
  private readonly http = inject(HttpClient);

  list(q: QueueQuery = {}): Observable<QueuePage> {
    return this.http.get<QueuePage>('/api/patient-queue', {
      params: toParams({
        status: q.status,
        department: q.department,
        triage_category: q.triage_category,
        investigation_status: q.investigation_status,
        min_wait_minutes: q.min_wait_minutes,
        max_wait_minutes: q.max_wait_minutes,
        arrived_within_minutes: q.arrived_within_minutes,
        page: q.page,
        page_size: q.page_size,
      }),
    });
  }

  waitingMetrics(department?: string, windowMinutes?: number): Observable<WaitingMetrics> {
    return this.http.get<WaitingMetrics>('/api/patient-queue/waiting-metrics', {
      params: toParams({ department, window_minutes: windowMinutes }),
    });
  }

  pendingInvestigations(department?: string, limit = 50): Observable<PendingInvestigations> {
    return this.http.get<PendingInvestigations>('/api/patient-queue/pending-investigations', {
      params: toParams({ department, limit }),
    });
  }
}
