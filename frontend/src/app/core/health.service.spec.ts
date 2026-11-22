import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { HealthService, HealthStatus } from './health.service';

describe('HealthService', () => {
  let service: HealthService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(HealthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('reports everything up when backend, database and pgvector are healthy', () => {
    let result: HealthStatus | undefined;
    service.check().subscribe((s) => (result = s));
    http.expectOne('/api/health').flush({ status: 'ok' });
    http.expectOne('/api/health/db').flush({ status: 'ok', pgvector: true });
    expect(result).toEqual({ backend: 'up', database: 'up', pgvector: 'up' });
  });

  it('reports pgvector down when the extension is missing', () => {
    let result: HealthStatus | undefined;
    service.check().subscribe((s) => (result = s));
    http.expectOne('/api/health').flush({ status: 'ok' });
    http.expectOne('/api/health/db').flush({ status: 'ok', pgvector: false });
    expect(result?.pgvector).toBe('down');
  });

  it('reports backend down and the rest unknown when the API is unreachable', () => {
    let result: HealthStatus | undefined;
    service.check().subscribe((s) => (result = s));
    http.expectOne('/api/health').error(new ProgressEvent('error'));
    http.expectOne('/api/health/db').error(new ProgressEvent('error'));
    expect(result).toEqual({ backend: 'down', database: 'unknown', pgvector: 'unknown' });
  });
});
