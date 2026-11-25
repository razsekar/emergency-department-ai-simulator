import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { CitationCheck } from '../features/agent/agent.models';
import { AnswerParagraph, parseAnswer } from '../features/agent/answer-parser';

/**
 * Renders a model answer with policy-backed paragraphs (those carrying a [Source: …] marker) visibly distinct from
 * uncited text. Citation chips show the backend's verification result. When no backend check is available
 * (`check` is null) the chips are neutral: the frontend never decides on its own whether a citation is real.
 */
@Component({
  selector: 'app-answer-view',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (paragraphs().length === 0) {
      <p class="muted">No answer text.</p>
    } @else {
      @for (p of paragraphs(); track $index) {
        <div class="para" [attr.data-kind]="p.kind" [attr.data-state]="paragraphState(p)">
          @if (!p.heading) {
            <span class="tag">{{ tagFor(p) }}</span>
          }
          <p>
            @for (s of p.segments; track $index) {
              @if (s.kind === 'citation') {
                <span class="cite" [attr.data-state]="stateOf(s.verified)" [title]="titleOf(s.verified)">{{ s.text }}</span>
              } @else {
                {{ s.text }}
              }
            }
          </p>
        </div>
      }
    }
  `,
  styles: `
    .para { margin: 0 0 10px; padding: 6px 10px; border-left: 3px solid var(--mat-sys-outline-variant); }
    .para[data-state='ok'] { border-left-color: #1f6f43; background: #eef7f1; }
    .para[data-state='bad'] { border-left-color: #b3261e; background: #fdf3f2; }
    .para[data-state='unknown'] { border-left-color: #1f5fa8; background: #eef3fa; }
    .tag { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; opacity: 0.7; margin-bottom: 2px; }
    p { margin: 0; white-space: pre-wrap; font-size: 14px; line-height: 1.45; }
    .cite { display: inline-block; padding: 0 6px; border-radius: 10px; font-size: 12px; font-weight: 500; background: #e8eef7; color: #1f3a5f; }
    .cite[data-state='ok'] { background: #d6efdf; color: #14502f; }
    .cite[data-state='bad'] { background: #fdecea; color: #8a1c14; text-decoration: line-through; }
    .muted { color: var(--mat-sys-on-surface-variant); }
  `,
})
export class AnswerView {
  readonly answer = input<string | null>(null);
  readonly check = input<CitationCheck | null>(null);

  protected readonly paragraphs = computed(() => parseAnswer(this.answer(), this.check()));

  /** uncited paragraphs have no state; cited ones are ok / bad / unknown according to the backend's check. */
  protected paragraphState(p: AnswerParagraph): 'none' | 'ok' | 'bad' | 'unknown' {
    if (p.kind === 'general') return 'none';
    const cites = p.segments.filter((s) => s.kind === 'citation');
    if (!this.check()) return 'unknown';
    return cites.every((c) => c.verified) ? 'ok' : 'bad';
  }

  protected tagFor(p: AnswerParagraph): string {
    switch (this.paragraphState(p)) {
      case 'ok':
        return 'Cites retrieved policy (verified)';
      case 'bad':
        return 'Cites a source that was NOT retrieved (unverified)';
      case 'unknown':
        return 'Cites a policy (not checked here)';
      default:
        // All the app knows: no [Source] marker. The text may be live data, so do not call it a general explanation.
        return 'No policy citation';
    }
  }

  protected stateOf(verified: boolean | undefined): 'ok' | 'bad' | 'unknown' {
    if (!this.check()) return 'unknown';
    return verified ? 'ok' : 'bad';
  }

  protected titleOf(verified: boolean | undefined): string {
    const state = this.stateOf(verified);
    if (state === 'ok') return 'Verified: this document and page were actually retrieved';
    if (state === 'bad') return 'NOT verified: this document/page was not among the retrieved chunks';
    return 'Citation not checked here (no verification data loaded)';
  }
}
