import { formatMetric, labelFromKey, parseAnswer } from './answer-parser';

const CHECK = {
  citations: [
    { document: 'Hospital Escalation Procedures', page: 2, verified: true },
    { document: 'Made Up', page: 9, verified: false },
  ],
};

describe('parseAnswer', () => {
  it('returns nothing for empty answers', () => {
    expect(parseAnswer(null)).toEqual([]);
    expect(parseAnswer('   ')).toEqual([]);
  });

  it('marks paragraphs with a citation as policy-backed and the rest as general explanation', () => {
    const p = parseAnswer('Escalate now [Source: Hospital Escalation Procedures, p.2].\n\nGeneral remark.', CHECK);
    expect(p.map((x) => x.kind)).toEqual(['policy', 'general']);
  });

  it('takes verification from the backend check, never from the text', () => {
    const p = parseAnswer('A [Source: Hospital Escalation Procedures, p.2]. B [Source: Made Up, p.9].', CHECK);
    const cites = p[0].segments.filter((s) => s.kind === 'citation');
    expect(cites.map((c) => c.verified)).toEqual([true, false]);
  });

  it('matches document names loosely (case, .pdf suffix, punctuation) like the backend does', () => {
    const p = parseAnswer('X [Source: hospital_escalation procedures.pdf, p. 2]', CHECK);
    expect(p[0].segments.find((s) => s.kind === 'citation')?.verified).toBe(true);
  });

  it('treats every citation as unverified when no check is available', () => {
    const p = parseAnswer('X [Source: Hospital Escalation Procedures, p.2]');
    expect(p[0].segments.find((s) => s.kind === 'citation')?.verified).toBe(false);
  });

  it('keeps the surrounding text in order', () => {
    const p = parseAnswer('before [Source: A, p.1] after', null);
    expect(p[0].segments.map((s) => s.kind)).toEqual(['text', 'citation', 'text']);
    expect(p[0].segments[0].text).toBe('before ');
    expect(p[0].segments[2].text).toBe(' after');
  });
});

describe('metric formatting', () => {
  it('humanises keys and formats numbers', () => {
    expect(labelFromKey('avg_wait_minutes')).toBe('Avg wait minutes');
    expect(formatMetric(75)).toBe('75');
    expect(formatMetric(91.666)).toBe('91.7');
    expect(formatMetric(null)).toBe('—');
  });
});
