import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { metrics } from '../testing/fixtures';
import { DashboardService, bucketForWindow } from './dashboard.service';

describe('DashboardService', () => {
  let http: HttpTestingController;
  let service: DashboardService;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(DashboardService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('requests metrics with the analysis window and bucket size', () => {
    let got: number | undefined;
    service.metrics(120, 15).subscribe((m) => (got = m.total_visits));
    const req = http.expectOne((r) => r.url === '/api/dashboard/metrics');
    expect(req.request.params.get('window_minutes')).toBe('120');
    expect(req.request.params.get('bucket_minutes')).toBe('15');
    req.flush(metrics());
    expect(got).toBe(40);
  });

  it('issues a fresh request on every call (no client-side caching)', () => {
    service.metrics().subscribe();
    service.metrics().subscribe();
    const reqs = http.match((r) => r.url === '/api/dashboard/metrics');
    expect(reqs.length).toBe(2);
    reqs.forEach((r) => r.flush(metrics()));
  });
});

describe('bucketForWindow', () => {
  it('stays within the backend limits of 5–120 minutes', () => {
    for (const w of [30, 60, 120, 240, 480, 1440]) {
      const b = bucketForWindow(w);
      expect(b).toBeGreaterThanOrEqual(5);
      expect(b).toBeLessThanOrEqual(120);
      expect(b % 5).toBe(0);
    }
    expect(bucketForWindow(240)).toBe(30);
    expect(bucketForWindow(1440)).toBe(120);
  });
});
