import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AuthService } from '../../core/auth/auth.service';
import { DEMO_QUESTION, MODELS, RUN_PAGE, STATUSES, runResponse } from '../testing/agent-fixtures';
import { AgentPage } from './agent.page';
import { AgentRunView } from './agent-run-view.component';

describe('AgentPage', () => {
  let http: HttpTestingController;
  let fixture: ComponentFixture<AgentPage>;
  let el: HTMLElement;

  const settle = async () => {
    await fixture.whenStable();
    fixture.detectChanges();
  };

  const load = async () => {
    http.expectOne((r) => r.url === '/api/providers/status').flush(STATUSES);
    http.expectOne('/api/providers/models').flush(MODELS);
    http.expectOne((r) => r.url === '/api/agent/runs').flush(RUN_PAGE);
    await settle();
  };

  const setup = async (canRun: boolean) => {
    TestBed.configureTestingModule({ imports: [AgentPage], providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    vi.spyOn(TestBed.inject(AuthService), 'hasPermission').mockImplementation((p) => canRun && p === 'agent:run');
    fixture = TestBed.createComponent(AgentPage);
    el = fixture.nativeElement;
    fixture.detectChanges();
    await load();
  };

  afterEach(() => http.verify());

  it('explains that the agent:run permission is needed and disables Run when it is missing', async () => {
    await setup(false);
    expect(el.textContent).toContain('agent:run');
    const run = [...el.querySelectorAll('button')].find((b) => b.textContent?.includes('Run agent')) as HTMLButtonElement;
    expect(run.disabled).toBe(true);
  });

  it('fills the textarea from the backend’s fixed question, runs the agent and shows the result', async () => {
    await setup(true);
    const preset = [...el.querySelectorAll('button')].find((b) => b.textContent?.includes('fixed demonstration question')) as HTMLButtonElement;
    preset.click();
    http.expectOne('/api/agent/demo-question').flush({ question: DEMO_QUESTION });
    await settle();
    expect((el.querySelector('textarea') as HTMLTextAreaElement).value).toBe(DEMO_QUESTION);

    const run = [...el.querySelectorAll('button')].find((b) => b.textContent?.includes('Run agent')) as HTMLButtonElement;
    expect(run.disabled).toBe(false);
    run.click();
    const req = http.expectOne('/api/agent/run');
    expect(req.request.body).toMatchObject({ question: DEMO_QUESTION, provider: 'ollama', model: 'qwen3:8b', mode: 'auto' });
    req.flush(runResponse());
    http.expectOne((r) => r.url === '/api/agent/runs').flush(RUN_PAGE); // history refreshes after a run
    await settle();

    expect(el.querySelector('app-agent-run-view')).not.toBeNull();
    expect(el.textContent).toContain('Emergency Surge');
    expect(el.textContent).toContain('get_bed_availability');
  });

  it('shows a readable error when the run fails', async () => {
    await setup(true);
    (el.querySelector('textarea') as HTMLTextAreaElement).value = 'What is happening?';
    (el.querySelector('textarea') as HTMLTextAreaElement).dispatchEvent(new Event('input'));
    await settle();
    const run = [...el.querySelectorAll('button')].find((b) => b.textContent?.includes('Run agent')) as HTMLButtonElement;
    run.click();
    http
      .expectOne('/api/agent/run')
      .flush({ error: { code: 'provider_not_configured', message: 'Set OPENAI_API_KEY to use OpenAI.' } }, { status: 409, statusText: 'Conflict' });
    await settle();
    expect(el.querySelector('.error')?.textContent).toContain('Set OPENAI_API_KEY');
  });

  it('lists history and opens a run from /runs/{id}', async () => {
    await setup(true);
    expect(el.textContent).toContain('1–1 of 21');
    const view = [...el.querySelectorAll('table.runs button')].find((b) => b.textContent?.includes('View')) as HTMLButtonElement;
    view.click();
    http.expectOne('/api/agent/runs/run-1').flush(runResponse({ scenario_name: 'Normal Operations', scenario_key: 'normal', data_version: 1 }));
    await settle();
    expect(el.querySelector('app-agent-run-view')?.textContent).toContain('Normal Operations');
  });

  it('pages through history with limit/offset', async () => {
    await setup(true);
    const next = [...el.querySelectorAll('.pager button')].find((b) => b.textContent?.includes('Next')) as HTMLButtonElement;
    next.click();
    const req = http.expectOne((r) => r.url === '/api/agent/runs');
    expect(req.request.params.get('offset')).toBe('10');
    req.flush({ ...RUN_PAGE, offset: 10 });
  });
});

describe('AgentRunView', () => {
  const render = (run = runResponse()) => {
    TestBed.configureTestingModule({ imports: [AgentRunView] });
    const f = TestBed.createComponent(AgentRunView);
    f.componentRef.setInput('run', run);
    f.detectChanges();
    return f.nativeElement as HTMLElement;
  };

  it('shows scenario, data version, native mode, tools with args and failed-tool status', () => {
    const el = render();
    expect(el.textContent).toContain('Emergency Surge · data v2');
    expect(el.textContent).toContain('Native tool calling');
    expect(el.querySelectorAll('.tools li').length).toBe(2);
    expect(el.querySelectorAll('.tstatus[data-status="invalid_arguments"]').length).toBe(1);
    expect(el.textContent).toContain('"status": "bogus"');
    expect(el.textContent).toContain('Patients waiting');
  });

  it('labels the labelled fallback mode and its reason', () => {
    const el = render(runResponse({ mode: 'fallback', fallback_reason: 'Tool calling is unknown for this model' }));
    expect(el.textContent).toContain('Fallback mode');
    expect(el.textContent).toContain('The model did not choose the tools');
    expect(el.textContent).toContain('Tool calling is unknown for this model');
  });

  it('separates policy-backed from general paragraphs and flags unverified citations', () => {
    const el = render();
    const kinds = [...el.querySelectorAll('.para')].map((p) => p.getAttribute('data-kind'));
    expect(kinds).toEqual(['policy', 'general', 'policy']);
    const uncited = el.querySelector('.para[data-kind="general"] .kind');
    expect(uncited?.textContent?.trim()).toBe('No policy citation');
    expect(el.querySelector('.legend')?.textContent).toContain('No policy citation');
    const cites = [...el.querySelectorAll('.cite')];
    expect(cites[0].getAttribute('data-verified')).toBe('true');
    expect(cites[1].getAttribute('data-verified')).toBe('false');
    expect(el.querySelector('.citecheck')?.textContent).toContain('1 verified, 1 unverified');
  });

  it('shows retrieved policies with page and score and marks flagged chunks', () => {
    const el = render();
    expect(el.textContent).toContain('Hospital Escalation Procedures');
    expect(el.textContent).toContain('page 2');
    expect(el.textContent).toContain('score 0.812');
    expect(el.querySelectorAll('.src.flagged').length).toBe(1);
    expect(el.textContent).toContain('withheld from the model');
  });

  it('does not invent cost or tokens, and warns on an inconsistent data version', () => {
    const el = render(runResponse({ data_version_consistent: false, usage: { prompt_tokens: null, completion_tokens: null, total_tokens: null } }));
    expect(el.textContent).toContain('not available');
    expect(el.querySelector('.warn')?.textContent).toContain('data version changed');
  });

  it('shows the error of a failed run', () => {
    const el = render(runResponse({ status: 'failed', error: 'The model never produced an answer.', answer: null }));
    expect(el.textContent).toContain('The model never produced an answer.');
    expect(el.textContent).toContain('No answer was produced.');
  });
});
