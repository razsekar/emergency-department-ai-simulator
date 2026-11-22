import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RetrievedPolicyView } from '../features/agent/agent.models';

/**
 * Retrieved hospital-policy excerpts (document, page, score, text). These come from the knowledge base,
 * not from the model. Chunks flagged by the backend's injection screen are shown but marked, and their
 * text was withheld from the model.
 */
@Component({
  selector: 'app-policy-sources',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (sources().length === 0) {
      <p class="muted">No policy excerpts were retrieved.</p>
    } @else {
      <ul class="list">
        @for (s of sources(); track $index) {
          <li class="src" [class.flagged]="s.flagged">
            <div class="head">
              <strong>{{ s.document_name }}</strong>
              <span>page {{ s.page }}</span>
              <span class="score" title="Cosine similarity">score {{ s.score.toFixed(3) }}</span>
              @if (s.flagged) {
                <span class="flag" role="note">Flagged: possible prompt injection, withheld from the model</span>
              }
            </div>
            <blockquote>{{ s.excerpt }}</blockquote>
            @if (showQuery()) {
              <div class="q">matched query: {{ s.matched_query }}</div>
            }
          </li>
        }
      </ul>
    }
  `,
  styles: `
    .list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
    .src { border: 1px solid var(--mat-sys-outline-variant); border-radius: 8px; padding: 8px 12px; }
    .src.flagged { border-color: #b3261e; background: #fdecea; }
    .head { display: flex; flex-wrap: wrap; gap: 12px; align-items: baseline; font-size: 13px; }
    .score { font-variant-numeric: tabular-nums; opacity: 0.75; }
    .flag { color: #8a1c14; font-weight: 500; }
    blockquote { margin: 6px 0 0; padding-left: 10px; border-left: 3px solid var(--mat-sys-outline-variant); font-size: 13px; white-space: pre-wrap; }
    .q { margin-top: 4px; font-size: 12px; opacity: 0.65; }
    .muted { color: var(--mat-sys-on-surface-variant); margin: 0; }
  `,
})
export class PolicySources {
  readonly sources = input.required<RetrievedPolicyView[]>();
  readonly showQuery = input(false);
}
