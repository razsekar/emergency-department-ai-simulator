import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { FIXED_QUESTION, demoRun, demoSession } from '../testing/demo-fixtures';
import { DemoService } from './demo.service';

describe('DemoService', () => {
  let service: DemoService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(DemoService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('reads the fixed question from the backend', () => {
    let got = '';
    service.question().subscribe((q) => (got = q));
    http.expectOne('/api/demo/question').flush({ question: FIXED_QUESTION });
    expect(got).toBe(FIXED_QUESTION);
  });

  it('posts only scenario, provider, model and options: the question is never sent by the client', () => {
    service.step({ scenario: 'surge', provider: 'ollama', model: 'model-a', temperature: 0.2, mode: 'auto' }).subscribe();
    const req = http.expectOne('/api/demo/step');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ scenario: 'surge', provider: 'ollama', model: 'model-a', temperature: 0.2, mode: 'auto' });
    expect(Object.keys(req.request.body)).not.toContain('question');
    req.flush({ run: demoRun(2, 'surge'), run_count: 2, metric_comparison: [] });
  });

  it('loads the saved session', () => {
    let count = -1;
    service.session().subscribe((s) => (count = s.run_count));
    http.expectOne('/api/demo/session').flush(demoSession([demoRun(1, 'normal')]));
    expect(count).toBe(1);
  });

  it('posts a reset', () => {
    service.reset().subscribe();
    const req = http.expectOne('/api/demo/session/reset');
    expect(req.request.method).toBe('POST');
    req.flush({ cleared_runs: 3, baseline_scenario: 'Normal Operations', data_version: 4 });
  });
});
