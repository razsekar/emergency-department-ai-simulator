import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AuthService } from '../../core/auth/auth.service';
import { CHECK_OK, DEMO_MODELS, DEMO_STATUSES, FIXED_QUESTION, demoRun, demoSession } from '../testing/demo-fixtures';
import { DemoPage } from './demo.page';

describe('DemoPage', () => {
  let http: HttpTestingController;
  let fixture: ComponentFixture<DemoPage>;
  let el: HTMLElement;

  const settle = async () => {
    await fixture.whenStable();
    fixture.detectChanges();
  };
  const button = (text: string) => [...el.querySelectorAll('button')].find((b) => b.textContent?.includes(text)) as HTMLButtonElement;
  const stepButton = (key: string) => el.querySelector(`[data-step="${key}"]`) as HTMLButtonElement;

  /** Flushes the four initial requests. `runs` are the already-saved demo runs. */
  const setup = async (permissions: string[], runs = [] as ReturnType<typeof demoRun>[]) => {
    TestBed.configureTestingModule({ imports: [DemoPage], providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    vi.spyOn(TestBed.inject(AuthService), 'hasPermission').mockImplementation((p) => permissions.includes(p));
    fixture = TestBed.createComponent(DemoPage);
    el = fixture.nativeElement;
    fixture.detectChanges();
    http.expectOne('/api/demo/question').flush({ question: FIXED_QUESTION });
    http.expectOne((r) => r.url === '/api/providers/status').flush(DEMO_STATUSES);
    http.expectOne('/api/providers/models').flush(DEMO_MODELS);
    http.expectOne('/api/demo/session').flush(demoSession(runs));
    for (const r of runs) http.expectOne(`/api/agent/runs/${r.analysis_run_id}`).flush({ citation_check: CHECK_OK });
    await settle();
  };

  afterEach(() => http.verify());

  const PRESENTER = ['scenario:apply', 'agent:run', 'scenario:reset'];

  it('shows the fixed question read-only and explains missing permissions', async () => {
    await setup([]);
    expect(el.querySelector('[data-testid="fixed-question"]')?.textContent).toContain(FIXED_QUESTION);
    expect(el.querySelector('textarea')).toBeNull(); // not editable
    expect(el.textContent).toContain('scenario:apply');
    expect(stepButton('surge').disabled).toBe(true);
    expect(el.textContent).toContain('No runs yet');
  });

  it('runs a step with the chosen model, then reloads the session and the toolbar state from the backend', async () => {
    await setup(PRESENTER);
    expect(stepButton('normal').textContent).toContain('Load Normal and Ask');
    expect(stepButton('surge').textContent).toContain('Load Surge and Ask');
    expect(stepButton('recovery').textContent).toContain('Load Recovery and Ask');
    expect(stepButton('surge').disabled).toBe(false);

    stepButton('surge').click();
    fixture.detectChanges();
    const req = http.expectOne('/api/demo/step');
    expect(req.request.body).toEqual({ scenario: 'surge', provider: 'ollama', model: 'model-a', temperature: 0.2, mode: 'auto' });
    expect(el.textContent).toContain('Applying Emergency Surge to the database'); // progress text while waiting
    expect(stepButton('normal').disabled).toBe(true); // no double submits

    const runs = [demoRun(1, 'normal'), demoRun(2, 'surge')];
    req.flush({ run: runs[1], run_count: 2, metric_comparison: [] });
    http.expectOne('/api/scenarios/current').flush({ scenario_key: 'surge', scenario_name: 'Emergency Surge', data_version: 2 });
    http.expectOne('/api/demo/session').flush(demoSession(runs));
    for (const r of runs) http.expectOne(`/api/agent/runs/${r.analysis_run_id}`).flush({ citation_check: CHECK_OK });
    await settle();

    expect(el.querySelectorAll('app-demo-run-column').length).toBe(2);
    expect(el.textContent).toContain('Run 1');
    expect(el.textContent).toContain('Emergency Surge');
    expect(el.textContent).toContain('v2');
    expect(el.textContent).toContain('102 patient records');
    expect(el.textContent).toContain('Data version v1 → v2');
    expect(el.textContent).toContain('Fixed question identical');
    expect(el.textContent).toContain('get_bed_availability');
    expect(el.textContent).toContain('Hospital Escalation Procedures');
    expect(el.textContent).toContain('ollama / model-a');
    expect(el.textContent).toContain('Tokens: 100 in / 50 out');
    expect(el.textContent).toContain('Cost: not available'); // never guessed
    expect(stepButton('surge').querySelector('[aria-label="A run for this scenario is saved"]')).not.toBeNull();
  });

  it('highlights metric rows that differ between runs and shows deltas from the backend diff block', async () => {
    await setup(PRESENTER, [demoRun(1, 'normal'), demoRun(2, 'surge'), demoRun(3, 'recovery')]);
    const rows = [...el.querySelectorAll('tbody tr')] as HTMLElement[];
    const waiting = rows.find((r) => r.textContent?.includes('Patients waiting'))!;
    expect(waiting.getAttribute('data-differs')).toBe('true');
    expect(waiting.textContent).toContain('12');
    expect(waiting.textContent).toContain('38');
    expect(waiting.textContent).toContain('(+26)');
    expect(waiting.textContent).toContain('(-29)');
    expect(el.querySelectorAll('app-demo-run-column').length).toBe(3);
  });

  it('marks citations using the backend check and separates policy-backed text from general explanation', async () => {
    await setup(PRESENTER, [demoRun(1, 'normal')]);
    const cite = el.querySelector('.cite') as HTMLElement;
    expect(cite.textContent).toContain('Hospital Escalation Procedures');
    expect(cite.getAttribute('data-state')).toBe('ok');
    expect(el.textContent).toContain('Cites retrieved policy');
    expect(el.textContent).toContain('No policy citation');
  });

  it('shows the backend message when a step fails (e.g. 409 verification) and re-enables the buttons', async () => {
    await setup(PRESENTER);
    stepButton('recovery').click();
    http.expectOne('/api/demo/step').flush(
      { error: { code: 'demo_verification_failed', message: 'Data version did not change; the question was not asked.' } },
      { status: 409, statusText: 'Conflict' },
    );
    http.expectOne('/api/scenarios/current').flush({ scenario_key: 'normal', scenario_name: 'Normal Operations', data_version: 1 });
    await settle();
    expect(el.querySelector('[data-testid="step-error"]')?.textContent).toContain('Data version did not change');
    expect(stepButton('recovery').disabled).toBe(false);
  });

  it('disables the steps and names the env var when the selected provider is not configured', async () => {
    await setup(PRESENTER);
    expect(el.textContent).not.toContain('Set OPENAI_API_KEY'); // ollama (configured) is selected by default
    expect(stepButton('normal').disabled).toBe(false);
  });

  it('asks for confirmation before reset, then clears and reloads the session', async () => {
    await setup(PRESENTER, [demoRun(1, 'normal')]);
    button('Reset and Replay').click();
    fixture.detectChanges();
    expect(el.textContent).toContain('This deletes 1 saved demo run(s)');
    http.expectNone('/api/demo/session/reset'); // nothing happens until confirmed

    button('Confirm reset').click();
    http.expectOne('/api/demo/session/reset').flush({ cleared_runs: 1, baseline_scenario: 'Normal Operations', data_version: 5 });
    http.expectOne('/api/demo/session').flush(demoSession([]));
    http.expectOne('/api/scenarios/current').flush({ scenario_key: 'normal', scenario_name: 'Normal Operations', data_version: 5 });
    await settle();
    expect(el.textContent).toContain('Reset: cleared 1 run(s)');
    expect(el.textContent).toContain('No runs yet');
    expect(el.querySelectorAll('app-demo-run-column').length).toBe(0);
  });

  it('can cancel a reset without calling the backend', async () => {
    await setup(PRESENTER, [demoRun(1, 'normal')]);
    button('Reset and Replay').click();
    fixture.detectChanges();
    button('Cancel').click();
    fixture.detectChanges();
    expect(button('Reset and Replay')).toBeTruthy();
  });
});
