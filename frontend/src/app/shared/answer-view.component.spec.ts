import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CitationCheck } from '../features/agent/agent.models';
import { AnswerView } from './answer-view.component';

const ANSWER =
  'Waiting is high [Source: Hospital Escalation Procedures, p.2].\n\n' +
  'Queues can raise walk-out risk.\n\n' +
  'Open an extra bay [Source: Made Up Doc, p.9].';

describe('AnswerView', () => {
  let fixture: ComponentFixture<AnswerView>;
  let el: HTMLElement;

  const render = async (check: CitationCheck | null) => {
    fixture = TestBed.createComponent(AnswerView);
    fixture.componentRef.setInput('answer', ANSWER);
    fixture.componentRef.setInput('check', check);
    await fixture.whenStable();
    el = fixture.nativeElement;
  };
  const states = () => [...el.querySelectorAll('.para')].map((p) => p.getAttribute('data-state'));

  it('uses the backend check: verified paragraph is ok, invented citation is bad, uncited text is general', async () => {
    await render({
      citations: [
        { document: 'Hospital Escalation Procedures', page: 2, verified: true },
        { document: 'Made Up Doc', page: 9, verified: false },
      ],
    });
    expect(states()).toEqual(['ok', 'none', 'bad']);
    expect(el.textContent).toContain('Cites retrieved policy (verified)');
    expect(el.textContent).toContain('Cites a source that was NOT retrieved (unverified)');
    expect(el.textContent).toContain('General explanation (not from policy)');
    expect([...el.querySelectorAll('.cite')].map((c) => c.getAttribute('data-state'))).toEqual(['ok', 'bad']);
  });

  it('never claims verification when no backend check is available', async () => {
    await render(null);
    expect(states()).toEqual(['unknown', 'none', 'unknown']);
    expect(el.textContent).toContain('not checked here');
    expect([...el.querySelectorAll('.cite')].map((c) => c.getAttribute('data-state'))).toEqual(['unknown', 'unknown']);
  });
});
