import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ScenarioService } from '../simulator/simulator.service';
import { applyResponse, metrics } from '../testing/fixtures';
import { DashboardPage } from './dashboard.page';

describe('DashboardPage', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [DashboardPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  const metricsRequests = () => http.match((r) => r.url === '/api/dashboard/metrics');
  const text = (el: HTMLElement, tile: string) =>
    el.querySelector(`[data-tile="${tile}"] .value`)?.textContent?.trim();

  it('shows every required metric from the API response and the data version', () => {
    const fixture = TestBed.createComponent(DashboardPage);
    fixture.detectChanges();
    http.expectOne('/api/scenarios/current').flush(applyResponse('normal', 'Normal Operations', 1).state);
    fixture.detectChanges();
    const [req] = metricsRequests();
    req.flush(metrics());
    fixture.detectChanges();

    const el: HTMLElement = fixture.nativeElement;
    expect(text(el, 'total-visits')).toBe('40');
    expect(text(el, 'waiting')).toBe('12');
    expect(text(el, 'in-treatment')).toBe('10');
    expect(text(el, 'beds-available')).toBe('8');
    expect(text(el, 'beds-occupied')).toBe('10');
    expect(text(el, 'avg-wait')).toBe('15.0 min');
    expect(text(el, 'critical')).toBe('3');
    expect(text(el, 'pending-investigations')).toBe('5');
    expect(text(el, 'discharges')).toBe('18');
    expect(el.querySelector('[data-test="meta"]')?.textContent).toContain('Normal Operations');
    expect(el.querySelector('[data-test="meta"]')?.textContent).toContain('data v1');
    expect(el.querySelectorAll('app-bar-chart').length).toBe(2);
    expect(el.querySelectorAll('[data-dept]').length).toBe(2);
    expect(el.querySelector('[data-meter="Beds"]')).not.toBeNull();
  });

  it('re-fetches fresh metrics when the data version changes (no stale numbers)', () => {
    const fixture = TestBed.createComponent(DashboardPage);
    fixture.detectChanges();
    http.expectOne('/api/scenarios/current').flush(applyResponse('normal', 'Normal Operations', 1).state);
    fixture.detectChanges();
    metricsRequests()[0].flush(metrics());
    fixture.detectChanges();
    expect(text(fixture.nativeElement, 'waiting')).toBe('12');

    TestBed.inject(ScenarioService).apply('surge').subscribe();
    http.expectOne('/api/scenarios/apply').flush(applyResponse('surge', 'Emergency Surge', 2));
    fixture.detectChanges();

    const reqs = metricsRequests();
    expect(reqs.length).toBe(1);
    reqs[0].flush(
      metrics({
        data_version: 2,
        scenario_key: 'surge',
        scenario_name: 'Emergency Surge',
        patients_waiting: 38,
        avg_wait_minutes: 75,
        beds: { total: 16, occupied: 15, available: 1, utilization_pct: 93.8 },
      }),
    );
    fixture.detectChanges();

    const el: HTMLElement = fixture.nativeElement;
    expect(text(el, 'waiting')).toBe('38');
    expect(text(el, 'avg-wait')).toBe('75.0 min');
    expect(text(el, 'beds-available')).toBe('1');
    expect(el.querySelector('[data-test="meta"]')?.textContent).toContain('Emergency Surge');
    expect(el.querySelector('[data-test="meta"]')?.textContent).toContain('data v2');
  });

  it('points to the simulator when the database is empty', () => {
    const fixture = TestBed.createComponent(DashboardPage);
    fixture.detectChanges();
    http.expectOne('/api/scenarios/current').flush({ data_version: 0, scenario_key: null, scenario_name: null, applied_at: null, last_run_id: null });
    fixture.detectChanges();
    metricsRequests()[0].flush(
      metrics({ data_version: 0, scenario_name: null, scenario_key: null, total_visits: 0 }),
    );
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('no patient records yet');
    expect(fixture.nativeElement.querySelector('a[href="/simulator"]')).not.toBeNull();
  });

  it('shows an error message when metrics cannot be loaded', () => {
    const fixture = TestBed.createComponent(DashboardPage);
    fixture.detectChanges();
    http.expectOne('/api/scenarios/current').flush(applyResponse('normal', 'Normal Operations', 1).state);
    fixture.detectChanges();
    metricsRequests()[0].flush({ error: { code: 'internal_error', message: 'Internal server error' } }, { status: 500, statusText: 'err' });
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alert"]')?.textContent).toContain('Internal server error');
  });
});
