import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, forkJoin, map, of } from 'rxjs';

export interface LiveResponse {
  status: string;
}

export interface DbHealthResponse {
  status: string;
  pgvector: boolean;
}

export type ServiceState = 'up' | 'down' | 'unknown';

export interface HealthStatus {
  backend: ServiceState;
  database: ServiceState;
  pgvector: ServiceState;
}

export const UNKNOWN_HEALTH: HealthStatus = {
  backend: 'unknown',
  database: 'unknown',
  pgvector: 'unknown',
};

@Injectable({ providedIn: 'root' })
export class HealthService {
  private readonly http = inject(HttpClient);

  /** Probes backend liveness and database/pgvector readiness. Never errors. */
  check(): Observable<HealthStatus> {
    return forkJoin({
      live: this.http.get<LiveResponse>('/api/health').pipe(catchError(() => of(null))),
      db: this.http.get<DbHealthResponse>('/api/health/db').pipe(catchError(() => of(null))),
    }).pipe(
      map(({ live, db }): HealthStatus => {
        const backend: ServiceState = live?.status === 'ok' ? 'up' : 'down';
        if (backend === 'down') {
          return { backend, database: 'unknown', pgvector: 'unknown' };
        }
        return {
          backend,
          database: db?.status === 'ok' ? 'up' : 'down',
          pgvector: db ? (db.pgvector ? 'up' : 'down') : 'unknown',
        };
      }),
    );
  }
}
