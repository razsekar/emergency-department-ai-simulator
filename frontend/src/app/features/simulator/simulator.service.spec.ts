import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { applyResponse } from '../testing/fixtures';
import { ScenarioService, apiErrorMessage } from './simulator.service';

describe('ScenarioService', () => {
  let service: ScenarioService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(ScenarioService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('has no data version until state is loaded', () => {
    expect(service.dataVersion()).toBeNull();
  });

  it('loads current state from the backend', () => {
    service.refreshState().subscribe();
    http.expectOne('/api/scenarios/current').flush(applyResponse('normal', 'Normal Operations', 3).state);
    expect(service.dataVersion()).toBe(3);
    expect(service.state()?.scenario_name).toBe('Normal Operations');
  });

  it('applies a built-in scenario without overrides and adopts the server state', () => {
    service.apply('surge').subscribe();
    const req = http.expectOne('/api/scenarios/apply');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ scenario_key: 'surge' });
    req.flush(applyResponse('surge', 'Emergency Surge', 4));
    expect(service.dataVersion()).toBe(4);
  });

  it('sends overrides for manual edits', () => {
    service.apply('normal', { beds_available: 2 }).subscribe();
    const req = http.expectOne('/api/scenarios/apply');
    expect(req.request.body).toEqual({ scenario_key: 'normal', overrides: { beds_available: 2 } });
    req.flush(applyResponse('custom', 'Custom Scenario', 5));
    expect(service.state()?.scenario_key).toBe('custom');
  });

  it('randomizes and resets via POST', () => {
    service.randomize().subscribe();
    http.expectOne('/api/scenarios/randomize').flush(applyResponse('custom', 'Randomized', 6));
    service.reset().subscribe();
    http.expectOne('/api/scenarios/reset').flush(applyResponse('normal', 'Normal Operations', 7));
    expect(service.dataVersion()).toBe(7);
  });

  it('keeps the previous state when an apply fails', () => {
    service.refreshState().subscribe();
    http.expectOne('/api/scenarios/current').flush(applyResponse('normal', 'Normal Operations', 3).state);
    service.apply('surge').subscribe({ error: () => undefined });
    http.expectOne('/api/scenarios/apply').flush({ error: { code: 'x', message: 'bad' } }, { status: 422, statusText: 'x' });
    expect(service.dataVersion()).toBe(3);
  });

  it('requests history with paging params', () => {
    service.history(10, 20).subscribe();
    const req = http.expectOne((r) => r.url === '/api/scenarios/history');
    expect(req.request.params.get('limit')).toBe('10');
    expect(req.request.params.get('offset')).toBe('20');
    req.flush({ items: [], total: 0, limit: 10, offset: 20 });
  });
});

describe('apiErrorMessage', () => {
  const err = (body: unknown, status = 400) => new HttpErrorResponse({ error: body, status });

  it('reads the app error shape', () => {
    expect(apiErrorMessage(err({ error: { code: 'c', message: 'Scenario invalid' } }))).toBe('Scenario invalid');
  });
  it('reads FastAPI string and list details', () => {
    expect(apiErrorMessage(err({ detail: 'nope' }))).toBe('nope');
    expect(apiErrorMessage(err({ detail: [{ msg: 'a' }, { msg: 'b' }] }, 422))).toBe('a; b');
  });
  it('reports an unreachable backend', () => {
    expect(apiErrorMessage(err(null, 0))).toBe('Backend is unreachable.');
  });
  it('falls back for unknown errors', () => {
    expect(apiErrorMessage(new Error('x'))).toBe('Unexpected error.');
  });
});
