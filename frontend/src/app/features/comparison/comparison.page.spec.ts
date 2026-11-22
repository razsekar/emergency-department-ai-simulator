import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AuthService } from '../../core/auth/auth.service';
import {
  COMPARISON_HISTORY,
  DEMO_MODELS,
  DEMO_STATUSES,
  FIXED_QUESTION,
  comparisonRun,
  modelResult,
} from '../testing/demo-fixtures';
import { ComparisonPage } from './comparison.page';

describe('ComparisonPage', () => {
  let http: HttpTestingController;
  let fixture: ComponentFixture<ComparisonPage>;
  let el: HTMLElement;

  const settle = async () => {
    await fixture.whenStable();
    fixture.detectChanges();
  };
  const checkboxes = () => [...el.querySelectorAll('mat-checkbox input')] as HTMLInputElement[];
  const runButton = () => [...el.querySelectorAll('button')].find((b) => b.textContent?.includes('Run comparison')) as HTMLButtonElement;

  const setup = async (canRun: boolean) => {
    TestBed.configureTestingModule({ imports: [ComparisonPage], providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    vi.spyOn(TestBed.inject(AuthService), 'hasPermission').mockImplementation((p) => canRun && p === 'comparison:run');
    fixture = TestBed.createComponent(ComparisonPage);
    el = fixture.nativeElement;
    fixture.detectChanges();
    http.expectOne((r) => r.url === '/api/providers/status').flush(DEMO_STATUSES);
    http.expectOne('/api/providers/models').flush(DEMO_MODELS);
    http.expectOne('/api/demo/question').flush({ question: FIXED_QUESTION });
    http.expectOne((r) => r.url === '/api/comparison/runs').flush(COMPARISON_HISTORY);
    await settle();
  };

  /** Selects the two configured models and runs, flushing the given result. */
  const runWith = async (result = comparisonRun()) => {
    checkboxes()[0].click();
    checkboxes()[1].click();
    fixture.detectChanges();
    runButton().click();
    const req = http.expectOne('/api/comparison/run');
    req.flush(result);
    http.expectOne((r) => r.url === '/api/comparison/runs').flush(COMPARISON_HISTORY); // history refresh
    await settle();
    return req;
  };

  afterEach(() => http.verify());

  it('always shows the "not a formal benchmark" label', async () => {
    await setup(true);
    expect(el.querySelector('[data-testid="demo-label"]')?.textContent).toContain('Demonstration comparison, not a formal benchmark.');
  });

  it('disables unconfigured models with the reason and requires at least two selections', async () => {
    await setup(true);
    const boxes = checkboxes();
    expect(boxes.length).toBe(3);
    expect(boxes[2].disabled).toBe(true);
    expect(el.textContent).toContain('Set OPENAI_API_KEY on the backend.');
    expect(runButton().disabled).toBe(true);
    boxes[0].click();
    fixture.detectChanges();
    expect(runButton().disabled).toBe(true); // one model is not a comparison
    checkboxes()[1].click();
    fixture.detectChanges();
    expect(runButton().disabled).toBe(false);
  });

  it('explains the missing permission and keeps Run disabled', async () => {
    await setup(false);
    expect(el.textContent).toContain('comparison:run');
    checkboxes()[0].click();
    checkboxes()[1].click();
    fixture.detectChanges();
    expect(runButton().disabled).toBe(true);
  });

  it('sends the chosen selections and the fixed question, then shows side-by-side cards with the shared snapshot', async () => {
    await setup(true);
    const req = await runWith();
    expect(req.request.body).toEqual({
      question: FIXED_QUESTION,
      selections: [
        { provider: 'ollama', model: 'model-a' },
        { provider: 'ollama', model: 'model-b' },
      ],
    });
    expect(el.querySelectorAll('article.card').length).toBe(2);
    expect(el.textContent).toContain('Emergency Surge');
    expect(el.textContent).toContain('v2');
    expect(el.querySelector('[data-testid="identical-indicator"]')?.textContent).toContain('Verified: every model received the identical prompt');
    expect(el.textContent).toContain('Accuracy');
    expect(el.textContent).toContain('50%');
    expect(el.textContent).toContain('Latency: 900 ms');
    expect(el.textContent).toContain('Cost: not available'); // cost is never guessed
    expect(el.textContent).toContain('Tokens: 100 in / 50 out');
    expect(el.querySelector('.cite')?.getAttribute('data-state')).toBe('ok');
  });

  it('lists numbers that contradict the snapshot, with the true value', async () => {
    await setup(true);
    const bad = modelResult(2, {
      scores: {
        accuracy: { score: 0, correct: 0, wrong: 1, not_mentioned: 7, wrong_numbers: { avg_wait_minutes: [60] } },
        completeness: { score: 0.5 },
        relevance: { score: 0.5 },
        citation_correctness: { score: null, no_citations: true },
      },
    });
    await runWith(comparisonRun({ results: [modelResult(1), bad] }));
    const wrong = el.querySelector('[data-testid="wrong-numbers"]')!;
    expect(wrong.textContent).toContain('Avg wait minutes: stated 60, true value 75');
    expect(el.textContent).toContain('n/a'); // null score shown as not applicable, not 0%
  });

  it('shows a per-model error without hiding the other models, and the partial-run warning', async () => {
    await setup(true);
    const failed = modelResult(2, { status: 'failed', error: 'Model timed out.', answer: null, latency_ms: null, scores: {} });
    await runWith(comparisonRun({ status: 'partial', results: [modelResult(1), failed] }));
    expect(el.textContent).toContain('Model timed out.');
    expect(el.textContent).toContain('Some models failed');
    expect(el.querySelectorAll('article.card').length).toBe(2);
    expect(el.textContent).toContain('Latency: not available');
  });

  it('warns when the data version changed during the run or the context could not be verified as identical', async () => {
    await setup(true);
    await runWith(comparisonRun({ data_version_consistent: false, identical_context_verified: false }));
    expect(el.querySelector('[data-testid="version-warning"]')?.textContent).toContain('data version changed');
    expect(el.querySelector('[data-testid="identical-indicator"]')?.textContent).toContain('NOT verified');
  });

  it('shows the backend message when the whole run is rejected (e.g. 409)', async () => {
    await setup(true);
    checkboxes()[0].click();
    checkboxes()[1].click();
    fixture.detectChanges();
    runButton().click();
    http.expectOne('/api/comparison/run').flush(
      { error: { code: 'no_models_available', message: 'None of the selected models can be used.' } },
      { status: 409, statusText: 'Conflict' },
    );
    await settle();
    expect(el.querySelector('[data-testid="run-error"]')?.textContent).toContain('None of the selected models can be used.');
    expect(runButton().disabled).toBe(false);
  });

  it('opens a past comparison from the history list', async () => {
    await setup(true);
    expect(el.textContent).toContain('Normal Operations');
    (el.querySelector('table.runs button') as HTMLButtonElement).click();
    http.expectOne('/api/comparison/runs/cmp-0').flush(comparisonRun({ id: 'cmp-0' }));
    await settle();
    expect(el.querySelectorAll('article.card').length).toBe(2);
  });
});
