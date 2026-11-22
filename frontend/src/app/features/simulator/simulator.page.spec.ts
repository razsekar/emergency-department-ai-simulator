import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AuthService } from '../../core/auth/auth.service';
import { applyResponse, NORMAL_PARAMS, SCENARIO_LIST } from '../testing/fixtures';
import { ScenarioStatusComponent } from './scenario-status.component';
import { SimulatorPage } from './simulator.page';

describe('SimulatorPage', () => {
  let http: HttpTestingController;
  let fixture: ComponentFixture<SimulatorPage>;
  let el: HTMLElement;

  const flushLoad = () => {
    http.expectOne('/api/scenarios/current').flush({ data_version: 1, scenario_key: 'normal', scenario_name: 'Normal Operations', applied_at: null, last_run_id: null });
    http.expectOne('/api/scenarios').flush(SCENARIO_LIST);
    http.expectOne((r) => r.url === '/api/scenarios/history').flush({ items: [], total: 0, limit: 10, offset: 0 });
    fixture.detectChanges();
  };

  const flushAfterApply = () => {
    http.expectOne((r) => r.url === '/api/scenarios/history').flush({ items: [applyResponse('surge', 'Emergency Surge', 2).run], total: 1, limit: 10, offset: 0 });
    http.expectOne('/api/scenarios').flush(SCENARIO_LIST);
    fixture.detectChanges();
  };

  const click = (test: string) => (el.querySelector(`[data-test="${test}"]`) as HTMLButtonElement).click();

  const PRESENTER = ['scenario:apply', 'scenario:reset'];

  const setup = (permissions: string[]) => {
    TestBed.configureTestingModule({
      imports: [SimulatorPage],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    vi.spyOn(TestBed.inject(AuthService), 'hasPermission').mockImplementation((p) => permissions.includes(p));
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(SimulatorPage);
    el = fixture.nativeElement;
    fixture.detectChanges();
    flushLoad();
  };

  beforeEach(() => setup(PRESENTER));

  afterEach(() => http.verify());

  it('shows the current scenario name and data version from the backend', () => {
    expect(el.textContent).toContain('Normal Operations');
    expect(el.textContent).toContain('v1');
  });

  it('Load Emergency Surge posts the surge scenario and shows the new data version', () => {
    click('load-surge');
    const req = http.expectOne('/api/scenarios/apply');
    expect(req.request.body).toEqual({ scenario_key: 'surge' });
    req.flush(applyResponse('surge', 'Emergency Surge', 2));
    flushAfterApply();
    expect(el.textContent).toContain('Emergency Surge');
    expect(el.textContent).toContain('Data version is now v2');
    expect(el.querySelector('.current')?.getAttribute('data-scenario')).toBe('surge');
  });

  it('Load Baseline and Load Recovery post the matching scenarios', () => {
    click('load-normal');
    http.expectOne('/api/scenarios/apply').flush(applyResponse('normal', 'Normal Operations', 2));
    flushAfterApply();
    click('load-recovery');
    expect(http.expectOne('/api/scenarios/apply').request.body).toEqual({ scenario_key: 'recovery' });
  });

  it('Randomize and Reset call their endpoints', () => {
    click('randomize');
    http.expectOne('/api/scenarios/randomize').flush(applyResponse('custom', 'Randomized Scenario', 2));
    flushAfterApply();
    click('reset');
    http.expectOne('/api/scenarios/reset').flush(applyResponse('normal', 'Normal Operations', 3));
    flushAfterApply();
    expect(el.textContent).toContain('Data version is now v3');
  });

  it('manual editor sends only the fields that changed, relative to the base scenario', () => {
    const input = el.querySelector('input[data-field="beds_available"]') as HTMLInputElement;
    expect(input.value).toBe(String(NORMAL_PARAMS.beds_available));
    input.value = '2';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    click('apply');
    const req = http.expectOne('/api/scenarios/apply');
    expect(req.request.body).toEqual({ scenario_key: 'normal', overrides: { beds_available: 2 } });
    req.flush(applyResponse('custom', 'Custom Scenario', 2));
    flushAfterApply();
    expect(el.textContent).toContain('Custom scenario applied');
  });

  it('applying the unedited editor sends the base scenario without overrides', () => {
    click('apply');
    expect(http.expectOne('/api/scenarios/apply').request.body).toEqual({ scenario_key: 'normal' });
  });

  it('blocks Apply when a value is out of range', () => {
    const input = el.querySelector('input[data-field="beds_available"]') as HTMLInputElement;
    input.value = '500';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    expect((el.querySelector('[data-test="apply"]') as HTMLButtonElement).disabled).toBe(true);
  });

  it('shows the backend validation message and says the database is unchanged when apply fails', () => {
    click('load-surge');
    http
      .expectOne('/api/scenarios/apply')
      .flush({ error: { code: 'scenario_invalid', message: 'window_minutes too small' } }, { status: 422, statusText: 'Unprocessable' });
    http.expectOne((r) => r.url === '/api/scenarios/history').flush({ items: [], total: 0, limit: 10, offset: 0 });
    fixture.detectChanges();
    expect(el.querySelector('.msg.error')?.textContent).toContain('window_minutes too small');
    expect(el.querySelector('.msg.error')?.textContent).toContain('database unchanged');
  });

  it('turns a 403 from the API into a friendly role message', () => {
    click('load-surge');
    http.expectOne('/api/scenarios/apply').flush({ error: { code: 'forbidden', message: 'forbidden' } }, { status: 403, statusText: 'Forbidden' });
    http.expectOne((r) => r.url === '/api/scenarios/history').flush({ items: [], total: 0, limit: 10, offset: 0 });
    fixture.detectChanges();
    expect(el.querySelector('.msg.error')?.textContent).toContain('Your role does not permit this action.');
  });
});

describe('ScenarioStatusComponent', () => {
  it('shows the scenario name and data version in the toolbar', () => {
    TestBed.configureTestingModule({
      imports: [ScenarioStatusComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    const http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(ScenarioStatusComponent);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Loading scenario');
    http.expectOne('/api/scenarios/current').flush({ data_version: 4, scenario_key: 'surge', scenario_name: 'Emergency Surge', applied_at: null, last_run_id: null });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Emergency Surge');
    expect(fixture.nativeElement.textContent).toContain('data v4');
    expect(fixture.nativeElement.querySelector('.pill').getAttribute('data-scenario')).toBe('surge');
    http.verify();
  });
});

describe('SimulatorPage for a viewer (no scenario permissions)', () => {
  it('disables every data-changing control and explains why', () => {
    TestBed.configureTestingModule({
      imports: [SimulatorPage],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    vi.spyOn(TestBed.inject(AuthService), 'hasPermission').mockReturnValue(false);
    const http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(SimulatorPage);
    fixture.detectChanges();
    http.expectOne('/api/scenarios/current').flush({ data_version: 1, scenario_key: 'normal', scenario_name: 'Normal Operations', applied_at: null, last_run_id: null });
    http.expectOne('/api/scenarios').flush(SCENARIO_LIST);
    http.expectOne((r) => r.url === '/api/scenarios/history').flush({ items: [], total: 0, limit: 10, offset: 0 });
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    for (const t of ['load-normal', 'load-surge', 'load-recovery', 'randomize', 'reset', 'apply']) {
      expect((el.querySelector(`[data-test="${t}"]`) as HTMLButtonElement).disabled, t).toBe(true);
    }
    expect(el.querySelector('[data-test="permission-note"]')?.textContent).toContain('cannot');
    http.verify();
  });
});
