import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';
import { AnswerView } from '../../shared/answer-view.component';
import { PolicySources } from '../../shared/policy-sources.component';
import { CitationCheck } from '../agent/agent.models';
import { formatMetric, labelFromKey, prettyJson } from '../agent/answer-parser';
import { formatCost, formatTokens } from '../playground/providers.service';
import { DemoRunView } from './demo.models';

/** One saved demo run (Run 1/2/3): verification evidence, tools, retrieved policy, answer and run facts. */
@Component({
  selector: 'app-demo-run-column',
  imports: [MatIconModule, AnswerView, PolicySources],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @let r = run();
    <article class="col" [attr.data-scenario]="r.scenario_key ?? 'none'" [attr.aria-label]="r.run_label">
      <header>
        <h3>{{ r.run_label }}</h3>
        <div class="scenario">{{ r.scenario_name ?? 'Unknown scenario' }}</div>
        <div class="facts">
          <span>Data version <strong>v{{ r.data_version }}</strong></span>
          <span><strong>{{ r.patient_record_count }}</strong> patient records</span>
        </div>
      </header>

      @if (r.verification; as v) {
        <section class="verify" aria-label="Verification">
          <h4>Verification</h4>
          <ul>
            <li [attr.data-ok]="v.data_version_changed">
              <mat-icon aria-hidden="true">{{ v.data_version_changed ? 'check_circle' : 'cancel' }}</mat-icon>
              Data version v{{ v.data_version_before }} → v{{ v.data_version_after }}
            </li>
            <li [attr.data-ok]="v.metrics_changed">
              <mat-icon aria-hidden="true">{{ v.metrics_changed ? 'check_circle' : 'remove_circle' }}</mat-icon>
              Metrics {{ v.metrics_changed ? 'changed' : 'did not change' }} vs
              {{ v.compared_to === 'previous_run' ? 'the previous run' : 'the state before this step' }}
            </li>
            <li [attr.data-ok]="v.question_identical">
              <mat-icon aria-hidden="true">{{ v.question_identical ? 'check_circle' : 'cancel' }}</mat-icon>
              Fixed question identical (byte for byte)
            </li>
            <li [attr.data-ok]="v.analysis_data_version_matches">
              <mat-icon aria-hidden="true">{{ v.analysis_data_version_matches ? 'check_circle' : 'cancel' }}</mat-icon>
              Agent analysed data v{{ v.data_version_after }}
            </li>
          </ul>
          @if (v.changed_metrics.length > 0) {
            <details>
              <summary>{{ v.changed_metrics.length }} changed metrics</summary>
              <ul class="changes">
                @for (c of v.changed_metrics; track c.metric) {
                  <li>{{ label(c.metric) }}: {{ fmt(c.before) }} → <strong>{{ fmt(c.after) }}</strong></li>
                }
              </ul>
            </details>
          }
          @if (v.note) {
            <p class="note">{{ v.note }}</p>
          }
        </section>
      }

      <section>
        <h4>Agent tools executed ({{ r.tools_executed.length }})</h4>
        @if (r.tools_executed.length === 0) {
          <p class="muted">No tools were executed.</p>
        } @else {
          <ol class="tools">
            @for (t of r.tools_executed; track t.sequence) {
              <li>
                <details>
                  <summary>
                    <code>{{ t.tool_name }}</code>
                    <span class="status" [attr.data-status]="t.status">{{ t.status }}</span>
                    <span class="muted">{{ t.duration_ms }} ms</span>
                  </summary>
                  <pre>args: {{ pretty(t.arguments) }}</pre>
                  @if (t.error) {
                    <p class="err">{{ t.error }}</p>
                  } @else {
                    <pre>result: {{ pretty(t.output) }}</pre>
                  }
                </details>
              </li>
            }
          </ol>
        }
      </section>

      <section>
        <h4>Retrieved policy documents ({{ r.retrieved_policies.length }})</h4>
        <details>
          <summary>Show excerpts</summary>
          <app-policy-sources [sources]="r.retrieved_policies" />
        </details>
        @if (docNames().length > 0) {
          <ul class="docs">
            @for (d of docNames(); track d) {
              <li>{{ d }}</li>
            }
          </ul>
        }
      </section>

      <section>
        <h4>Final response</h4>
        @if (r.final_answer) {
          <app-answer-view [answer]="r.final_answer" [check]="check()" />
        } @else {
          <p class="muted">The run produced no answer text.</p>
        }
      </section>

      <footer>
        <span>{{ r.provider }} / {{ r.model }}</span>
        <span>{{ r.latency_ms }} ms</span>
        <span>Tokens: {{ tokens(r) }}</span>
        <span>Cost: {{ cost(r) }}</span>
      </footer>
    </article>
  `,
  styles: `
    :host { display: block; min-width: 0; }
    .col { border: 1px solid var(--mat-sys-outline-variant); border-top-width: 4px; border-radius: 10px; padding: 12px 14px; background: var(--mat-sys-surface); height: 100%; }
    .col[data-scenario='normal'] { border-top-color: #1f6f43; }
    .col[data-scenario='surge'] { border-top-color: #b3261e; }
    .col[data-scenario='recovery'] { border-top-color: #1f5fa8; }
    h3 { margin: 0; font-size: 18px; }
    h4 { margin: 14px 0 6px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.04em; opacity: 0.75; }
    .scenario { font-weight: 600; margin-top: 2px; }
    .facts { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 13px; margin-top: 4px; }
    ul { margin: 0; padding-left: 0; list-style: none; }
    .verify li { display: flex; gap: 6px; align-items: center; font-size: 13px; margin: 2px 0; }
    .verify li[data-ok='true'] mat-icon { color: #1f6f43; }
    .verify li[data-ok='false'] mat-icon { color: #b3261e; }
    .verify mat-icon { font-size: 18px; width: 18px; height: 18px; }
    .changes { padding-left: 8px; font-size: 12px; }
    .tools { margin: 0; padding-left: 18px; font-size: 13px; }
    .tools summary { cursor: pointer; display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }
    .status { font-size: 11px; padding: 0 6px; border-radius: 8px; background: #d6efdf; color: #14502f; }
    .status:not([data-status='ok']) { background: #fdecea; color: #8a1c14; }
    pre { margin: 4px 0; padding: 6px 8px; background: var(--mat-sys-surface-container); border-radius: 6px; font-size: 11px; max-height: 160px; overflow: auto; white-space: pre-wrap; word-break: break-word; }
    .docs { font-size: 12px; margin-top: 6px; opacity: 0.85; }
    .docs li::before { content: '• '; }
    .muted { color: var(--mat-sys-on-surface-variant); font-size: 13px; margin: 0; }
    .err { color: #b3261e; font-size: 12px; margin: 4px 0; }
    .note { font-size: 12px; color: var(--mat-sys-on-surface-variant); margin: 6px 0 0; }
    footer { display: flex; flex-wrap: wrap; gap: 4px 14px; margin-top: 12px; padding-top: 8px; border-top: 1px solid var(--mat-sys-outline-variant); font-size: 12px; color: var(--mat-sys-on-surface-variant); }
  `,
})
export class DemoRunColumn {
  readonly run = input.required<DemoRunView>();
  /** Backend citation verification for this run's answer (null while loading or unavailable). */
  readonly check = input<CitationCheck | null>(null);

  protected docNames(): string[] {
    return [...new Set(this.run().retrieved_policies.map((p) => p.document_name))];
  }
  protected label = labelFromKey;
  protected fmt = formatMetric;
  protected pretty = prettyJson;
  protected tokens(r: DemoRunView): string {
    return formatTokens(r.usage);
  }
  protected cost(r: DemoRunView): string {
    return formatCost(r.estimated_cost_usd);
  }
}
