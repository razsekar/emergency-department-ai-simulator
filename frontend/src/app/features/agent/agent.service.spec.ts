import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { DEMO_QUESTION, RUN_PAGE, runResponse } from '../testing/agent-fixtures';
import { AgentService } from './agent.service';

describe('AgentService', () => {
  let http: HttpTestingController;
  let svc: AgentService;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    svc = TestBed.inject(AgentService);
  });
  afterEach(() => http.verify());

  it('fetches the fixed demonstration question from the backend', () => {
    let q = '';
    svc.demoQuestion().subscribe((v) => (q = v));
    http.expectOne('/api/agent/demo-question').flush({ question: DEMO_QUESTION });
    expect(q).toBe(DEMO_QUESTION);
  });

  it('posts a run request with the selected model settings', () => {
    let status = '';
    svc.run({ question: 'Q?', provider: 'ollama', model: 'm', temperature: 0.2, mode: 'auto' }).subscribe((r) => (status = r.status));
    const req = http.expectOne('/api/agent/run');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ question: 'Q?', provider: 'ollama', model: 'm', temperature: 0.2, mode: 'auto' });
    req.flush(runResponse());
    expect(status).toBe('completed');
  });

  it('lists history with paging and only filters by run_type when asked', () => {
    svc.runs(10, 20).subscribe();
    const all = http.expectOne((r) => r.url === '/api/agent/runs');
    expect(all.request.params.get('limit')).toBe('10');
    expect(all.request.params.get('offset')).toBe('20');
    expect(all.request.params.has('run_type')).toBe(false);
    all.flush(RUN_PAGE);

    svc.runs(10, 0, 'demo').subscribe();
    const demo = http.expectOne((r) => r.url === '/api/agent/runs');
    expect(demo.request.params.get('run_type')).toBe('demo');
    demo.flush(RUN_PAGE);
  });

  it('loads one run by id', () => {
    svc.runDetail('run-1').subscribe();
    http.expectOne('/api/agent/runs/run-1').flush(runResponse());
  });
});
