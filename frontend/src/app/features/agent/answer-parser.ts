import { CitationCheck } from './agent.models';

/** Matches the citation format the backend instructs the model to use (see domain/citations.py). */
const CITATION = /\[Source:\s*([^,\]]+?)\s*,\s*p\.?\s*(\d+)\s*\]/gi;

export interface AnswerSegment {
  kind: 'text' | 'citation';
  text: string;
  /** Only for citations: did the backend find this document + page among the retrieved chunks? */
  verified?: boolean;
}

export interface AnswerParagraph {
  /** 'policy' paragraphs carry at least one citation marker; 'general' ones do not. */
  kind: 'policy' | 'general';
  segments: AnswerSegment[];
}

function norm(name: string): string {
  return name
    .toLowerCase()
    .replace(/\.pdf$/, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

/** A citation is verified when the backend's own check lists it as verified (same normalised name and page). */
function isVerified(doc: string, page: number, check: CitationCheck | null | undefined): boolean {
  const items = check?.citations ?? [];
  return items.some((c) => c.verified && c.page === page && norm(c.document) === norm(doc));
}

/**
 * Splits a model answer into paragraphs and marks each as policy-backed (has a [Source: …] marker) or
 * general explanation (does not), so the UI can show which statements claim to come from retrieved policy.
 * Verification status comes from the backend's citation check; the frontend never decides it by itself.
 */
export function parseAnswer(answer: string | null | undefined, check?: CitationCheck | null): AnswerParagraph[] {
  if (!answer || !answer.trim()) return [];
  return answer
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter((p) => p.length > 0)
    .map((para) => {
      const segments: AnswerSegment[] = [];
      let last = 0;
      for (const m of para.matchAll(CITATION)) {
        const start = m.index ?? 0;
        if (start > last) segments.push({ kind: 'text', text: para.slice(last, start) });
        segments.push({ kind: 'citation', text: m[0], verified: isVerified(m[1], Number(m[2]), check) });
        last = start + m[0].length;
      }
      if (last < para.length) segments.push({ kind: 'text', text: para.slice(last) });
      const hasCitation = segments.some((s) => s.kind === 'citation');
      return { kind: hasCitation ? 'policy' : 'general', segments } as AnswerParagraph;
    });
}

/** "avg_wait_minutes" -> "Avg wait minutes". */
export function labelFromKey(key: string): string {
  const s = key.replace(/_/g, ' ');
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function formatMetric(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(1);
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function prettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}
