import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AuthService } from '../../core/auth/auth.service';
import { MODELS, STATUSES } from '../testing/agent-fixtures';
import { AssistantBackend, AssistantEvent, AssistantTurn } from './assistant-backend';
import { AssistantPage } from './assistant.page';

class FakeBackend extends AssistantBackend {
  readonly grounded = true;
  turns: AssistantTurn[] = [];
  resets = 0;
  async send(turn: AssistantTurn, onEvent: (e: AssistantEvent) => void): Promise<void> {
    this.turns.push(turn);
    onEvent({ type: 'sources', sources: [{ document_name: 'Hospital Escalation Procedures', page: 2, score: 0.81, excerpt: 'Escalate above 60 min.', matched_query: 'q', flagged: false }] });
    onEvent({ type: 'delta', content: 'Escalate now [Source: Hospital Escalation Procedures, p.2]. ' });
    onEvent({ type: 'delta', content: '[Source: Made Up, p.7]' });
    onEvent({
      type: 'done',
      meta: {
        provider: 'ollama', model: 'qwen3:8b', latency_ms: 800, usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 }, estimated_cost_usd: null,
        sources: [], data_disclosure: null,
        citation_check: { citations: [{ document: 'Hospital Escalation Procedures', page: 2, verified: true }, { document: 'Made Up', page: 7, verified: false }], verified_count: 1, unverified_count: 1 },
      },
    });
  }
  reset(): void {
    this.resets++;
  }
}

describe('AssistantPage (RAG-grounded)', () => {
  let http: HttpTestingController;
  let fixture: ComponentFixture<AssistantPage>;
  let el: HTMLElement;
  const backend = new FakeBackend();

  beforeEach(async () => {
    backend.turns = [];
    backend.resets = 0;
    TestBed.configureTestingModule({ imports: [AssistantPage], providers: [provideHttpClient(), provideHttpClientTesting()] });
    TestBed.overrideComponent(AssistantPage, { set: { providers: [{ provide: AssistantBackend, useValue: backend }] } });
    http = TestBed.inject(HttpTestingController);
    vi.spyOn(TestBed.inject(AuthService), 'hasPermission').mockReturnValue(true);
    fixture = TestBed.createComponent(AssistantPage);
    el = fixture.nativeElement;
    fixture.detectChanges();
    http.expectOne((r) => r.url === '/api/providers/status').flush(STATUSES);
    http.expectOne('/api/providers/models').flush(MODELS);
    await fixture.whenStable();
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  const ask = async (text: string) => {
    const ta = el.querySelector('textarea') as HTMLTextAreaElement;
    ta.value = text;
    ta.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    fixture.detectChanges();
    (el.querySelector('form button[type="submit"]') as HTMLButtonElement).click();
    await fixture.whenStable();
    fixture.detectChanges();
  };

  it('explains how grounding and citations work', () => {
    expect(el.querySelector('.notice')?.textContent).toContain('retrieved policy excerpts');
  });

  it('sends the new message plus the streaming choice to the backend', async () => {
    await ask('What is the escalation rule?');
    expect(backend.turns.length).toBe(1);
    expect(backend.turns[0].content).toBe('What is the escalation rule?');
    expect(backend.turns[0].streaming).toBe(true);
    expect(backend.turns[0].model.model_id).toBe('qwen3:8b');
  });

  it('shows the answer with verified and unverified citations, the sources and the citation check', async () => {
    await ask('What is the escalation rule?');
    const cites = [...el.querySelectorAll('.cite')];
    expect(cites.map((c) => c.getAttribute('data-verified'))).toEqual(['true', 'false']);
    expect(el.textContent).toContain('Retrieved policy excerpts (1)');
    expect(el.textContent).toContain('Escalate above 60 min.');
    expect(el.textContent).toContain('Citation check: 1 verified, 1 unverified');
    expect(el.textContent).toContain('not available'); // cost is never invented
  });

  it('starts a new conversation on request', async () => {
    await ask('Hello policy?');
    const btn = [...el.querySelectorAll('form button')].find((b) => b.textContent?.includes('New conversation')) as HTMLButtonElement;
    btn.click();
    fixture.detectChanges();
    expect(backend.resets).toBe(1);
    expect(el.querySelectorAll('.turn').length).toBe(0);
  });
});
