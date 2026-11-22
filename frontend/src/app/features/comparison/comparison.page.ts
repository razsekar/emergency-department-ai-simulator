import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { describeApiError } from '../../core/api-error';
import { AuthService } from '../../core/auth/auth.service';
import { AnswerView } from '../../shared/answer-view.component';
import { PolicySources } from '../../shared/policy-sources.component';
import { formatMetric, labelFromKey } from '../agent/answer-parser';
import { DemoService } from '../demo/demo.service';
import { CloudDisclosure } from '../playground/cloud-disclosure.component';
import { ModelInfo, ProvidersService, ProviderStatus, formatCost, formatTokens } from '../playground/providers.service';
import {
  COMPARISON_MAX_MODELS,
  COMPARISON_MIN_MODELS,
  ComparisonHistoryPage,
  ComparisonRunResponse,
  ModelResultView,
  ModelSelection,
} from './comparison.models';
import { ComparisonService } from './comparison.service';

const NEEDS_RUN = 'comparison:run';
const HISTORY_PAGE = 10;

const SCORE_LABELS = [
  ['accuracy', 'Accuracy'],
  ['completeness', 'Completeness'],
  ['relevance', 'Relevance'],
  ['citation_correctness', 'Citation correctness'],
] as const;

@Component({
  selector: 'app-comparison-page',
  imports: [
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatCheckboxModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressBarModule,
    CloudDisclosure,
    AnswerView,
    PolicySources,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1>Response Comparison</h1>
    <p class="label" role="note" data-testid="demo-label">
      <mat-icon aria-hidden="true">info</mat-icon>
      <strong>Demonstration comparison, not a formal benchmark.</strong>
      One question, one data snapshot, models answered one after another.
    </p>
    <p class="lead">
      The backend gathers the scenario data, tool results and policy excerpts <strong>once</strong>. Every selected model then
      answers from that identical frozen context, so differences come from the models, not from the data.
    </p>

    @if (loadError()) {
      <p class="error" role="alert">{{ loadError() }}</p>
    }
    @if (!canRun()) {
      <p class="notice" role="note">
        <mat-icon aria-hidden="true">lock</mat-icon>
        <span>Running a comparison needs the “comparison:run” permission. Sign in with a presenter or admin account.</span>
      </p>
    }

    <mat-card appearance="outlined">
      <mat-card-header><mat-card-title>1. Choose models ({{ selected().size }} selected, {{ min }}–{{ max }} allowed)</mat-card-title></mat-card-header>
      <mat-card-content>
        @if (models().length === 0) {
          <p class="muted">No models are listed yet. Configure a provider or start Ollama, then reload.</p>
        }
        <ul class="models">
          @for (m of models(); track m.provider + '|' + m.model_id) {
            <li [attr.data-configured]="isConfigured(m)">
              <mat-checkbox
                [checked]="isSelected(m)"
                [disabled]="!isConfigured(m) || (!isSelected(m) && selected().size >= max)"
                (change)="toggle(m, $event.checked)"
              >
                {{ providerLabel(m) }} / {{ m.display_name }}
              </mat-checkbox>
              @if (!isConfigured(m)) {
                <span class="reason">{{ reasonFor(m) }}</span>
              } @else if (m.cloud) {
                <span class="cloud">cloud</span>
              }
              @if (m.supports_tools !== null) {
                <span class="muted">tool calling: {{ m.supports_tools ? 'yes' : 'no' }}</span>
              }
            </li>
          }
        </ul>
        <app-cloud-disclosure [cloud]="anyCloud()" text="Selected cloud models receive the question, the scenario metrics and the retrieved policy excerpts." />
      </mat-card-content>
    </mat-card>

    <mat-card appearance="outlined">
      <mat-card-header><mat-card-title>2. Question</mat-card-title></mat-card-header>
      <mat-card-content>
        <mat-form-field appearance="outline" class="wide">
          <mat-label>Question (defaults to the fixed demonstration question)</mat-label>
          <textarea matInput rows="3" [ngModel]="question()" (ngModelChange)="question.set($event)" maxlength="2000"></textarea>
        </mat-form-field>
        <div class="actions">
          <button mat-stroked-button type="button" (click)="useFixedQuestion()" [disabled]="!fixedQuestion()">Use the fixed demonstration question</button>
          <button mat-flat-button type="button" (click)="run()" [disabled]="!canSubmit()">
            <mat-icon>compare</mat-icon> Run comparison
          </button>
          @if (!enoughModels()) {
            <span class="muted">Select at least {{ min }} configured models.</span>
          }
        </div>
        @if (busy()) {
          <div class="progress" role="status" aria-live="polite">
            <mat-progress-bar mode="indeterminate" />
            <p>Building the shared data snapshot, then asking each model in turn. Local models can take a minute each…</p>
          </div>
        }
        @if (runError()) {
          <p class="error" role="alert" data-testid="run-error">{{ runError() }}</p>
        }
      </mat-card-content>
    </mat-card>

    @if (result(); as r) {
      <section aria-label="Comparison result">
        <h2>Result</h2>
        <p class="label"><mat-icon aria-hidden="true">info</mat-icon><span>{{ r.label }} {{ r.scoring_note }}</span></p>

        @if (r.status !== 'completed') {
          <p class="warn" role="alert">
            <mat-icon aria-hidden="true">warning</mat-icon>
            <span>{{ r.status === 'partial' ? 'Some models failed or were not configured; see their cards.' : 'No model produced an answer.' }}</span>
          </p>
        }
        @if (!r.data_version_consistent) {
          <p class="warn" role="alert" data-testid="version-warning">
            <mat-icon aria-hidden="true">warning</mat-icon>
            <span>The simulation data version changed while the models were answering. Results are not comparable on identical data.</span>
          </p>
        }

        <mat-card appearance="outlined" class="shared">
          <mat-card-header><mat-card-title>Shared data snapshot (identical for every model)</mat-card-title></mat-card-header>
          <mat-card-content>
            <p class="facts">
              <span><strong>{{ r.shared_context.scenario_name ?? 'Unknown scenario' }}</strong></span>
              <span>data version <strong>v{{ r.shared_context.data_version ?? '?' }}</strong></span>
              <span>{{ r.shared_context.tools_executed.length }} tools executed once</span>
              <span>{{ r.shared_context.retrieved_policies.length }} policy excerpts retrieved once</span>
            </p>
            <p class="identical" [attr.data-ok]="r.identical_context_verified" data-testid="identical-indicator">
              <mat-icon aria-hidden="true">{{ r.identical_context_verified ? 'verified' : 'error' }}</mat-icon>
              @if (r.identical_context_verified) {
                Verified: every model received the identical prompt (SHA-256 {{ r.shared_context.context_sha256.slice(0, 16) }}…).
              } @else {
                NOT verified: at least one model received a different prompt than the shared context. Do not compare these answers.
              }
            </p>
            <div class="scroll">
              <table class="kv">
                <tbody>
                  @for (e of metricEntries(r); track e[0]) {
                    <tr><th scope="row">{{ label(e[0]) }}</th><td>{{ fmt(e[1]) }}</td></tr>
                  }
                </tbody>
              </table>
            </div>
            <details>
              <summary>Retrieved policy excerpts used by all models</summary>
              <app-policy-sources [sources]="r.shared_context.retrieved_policies" />
            </details>
          </mat-card-content>
        </mat-card>

        <div class="grid">
          @for (m of r.results; track m.position) {
            <article class="card" [attr.data-status]="m.status" [attr.aria-label]="m.provider + ' ' + m.model">
              <header>
                <h3>{{ m.provider }} / {{ m.model }}</h3>
                <span class="status" [attr.data-status]="m.status">{{ statusText(m.status) }}</span>
              </header>
              @if (m.status !== 'completed') {
                <p class="error" role="alert">{{ m.error ?? 'This model produced no answer.' }}</p>
              } @else {
                <div class="scores" aria-label="Demonstration scores">
                  @for (s of scoreLabels; track s[0]) {
                    <span class="score">
                      <span class="sname">{{ s[1] }}</span>
                      <strong>{{ pct(scoreOf(m, s[0])) }}</strong>
                    </span>
                  }
                </div>
                @if (wrongNumbers(m, r); as wn) {
                  @if (wn.length > 0) {
                    <div class="wrong" role="note" data-testid="wrong-numbers">
                      <strong>Numbers that do not match the snapshot:</strong>
                      <ul>
                        @for (w of wn; track w) {
                          <li>{{ w }}</li>
                        }
                      </ul>
                    </div>
                  }
                }
                <app-answer-view [answer]="m.answer" [check]="m.citation_check" />
              }
              <footer>
                <span>Latency: {{ m.latency_ms === null ? 'not available' : m.latency_ms + ' ms' }}</span>
                <span>Tokens: {{ tokens(m) }}</span>
                <span>Cost: {{ cost(m) }}</span>
                <span>Tool calling: {{ m.tool_calling_supported === null ? 'unknown' : m.tool_calling_supported ? 'yes' : 'no' }}</span>
              </footer>
            </article>
          }
        </div>
      </section>
    }

    <mat-card appearance="outlined" class="history">
      <mat-card-header><mat-card-title>History</mat-card-title></mat-card-header>
      <mat-card-content>
        @if (historyError()) {
          <p class="error" role="alert">{{ historyError() }}</p>
        }
        @if (history(); as h) {
          @if (h.items.length === 0) {
            <p class="muted">No comparisons recorded yet.</p>
          } @else {
            <div class="scroll">
              <table class="runs">
                <thead><tr><th>When</th><th>Scenario</th><th>Models</th><th>Status</th><th></th></tr></thead>
                <tbody>
                  @for (s of h.items; track s.id) {
                    <tr [class.selected]="s.id === result()?.id">
                      <td>{{ s.created_at }}</td>
                      <td>{{ s.scenario_name ?? '—' }} <span class="muted">v{{ s.data_version ?? '?' }}</span></td>
                      <td>{{ s.models.join(', ') }}</td>
                      <td>{{ s.status }}{{ s.data_version_consistent ? '' : ' · version changed' }}</td>
                      <td><button mat-button type="button" (click)="open(s.id)">View</button></td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
            <div class="pager">
              <button mat-button type="button" (click)="page(-1)" [disabled]="h.offset === 0">Previous</button>
              <span>{{ h.offset + 1 }}–{{ h.offset + h.items.length }} of {{ h.total }}</span>
              <button mat-button type="button" (click)="page(1)" [disabled]="h.offset + h.items.length >= h.total">Next</button>
            </div>
          }
        } @else if (!historyError()) {
          <p class="muted">Loading history…</p>
        }
      </mat-card-content>
    </mat-card>
  `,
  styles: `
    :host { display: block; max-width: 1500px; }
    h1 { margin: 0 0 4px; }
    h2 { margin: 24px 0 8px; }
    h3 { margin: 0; font-size: 16px; }
    .lead { margin: 0 0 12px; color: var(--mat-sys-on-surface-variant); max-width: 900px; }
    .label { display: flex; gap: 8px; align-items: center; padding: 8px 12px; border-radius: 8px; background: #fff4d6; border: 1px solid #e8c766; color: #5b4300; font-size: 14px; }
    mat-card { margin-bottom: 16px; }
    mat-card-content { padding-top: 12px; }
    .models { list-style: none; margin: 8px 0; padding: 0; display: flex; flex-direction: column; gap: 2px; }
    .models li { display: flex; flex-wrap: wrap; gap: 4px 12px; align-items: center; }
    .models li[data-configured='false'] { opacity: 0.7; }
    .reason { font-size: 12px; color: #8a1c14; }
    .cloud { font-size: 11px; padding: 0 6px; border-radius: 8px; background: #fff4e0; color: #5b3b00; }
    .wide { width: 100%; }
    .actions { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
    .progress p { margin: 6px 0 0; font-size: 14px; }
    .muted { color: var(--mat-sys-on-surface-variant); font-size: 13px; }
    .error { color: #b3261e; }
    .notice { display: flex; gap: 8px; align-items: center; padding: 8px 12px; border-radius: 8px; background: #e8eef7; color: #1f3a5f; font-size: 13px; }
    .warn { display: flex; gap: 8px; align-items: center; padding: 8px 12px; border-radius: 8px; background: #fdecea; color: #8a1c14; font-size: 14px; }
    .facts { display: flex; flex-wrap: wrap; gap: 4px 18px; margin: 4px 0 8px; font-size: 14px; }
    .identical { display: flex; gap: 6px; align-items: center; font-size: 13px; }
    .identical[data-ok='true'] { color: #14502f; }
    .identical[data-ok='false'] { color: #8a1c14; font-weight: 600; }
    .scroll { overflow-x: auto; }
    .kv { border-collapse: collapse; font-size: 13px; }
    .kv th, .kv td { text-align: left; padding: 3px 16px 3px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 380px), 1fr)); gap: 14px; align-items: start; }
    .card { border: 1px solid var(--mat-sys-outline-variant); border-radius: 10px; padding: 12px 14px; }
    .card[data-status='failed'], .card[data-status='not_configured'] { border-color: #b3261e; }
    .card header { display: flex; justify-content: space-between; gap: 8px; align-items: baseline; margin-bottom: 8px; }
    .status { font-size: 11px; padding: 0 8px; border-radius: 8px; background: #d6efdf; color: #14502f; }
    .status:not([data-status='completed']) { background: #fdecea; color: #8a1c14; }
    .scores { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-bottom: 8px; }
    .score { display: flex; flex-direction: column; font-size: 12px; }
    .sname { opacity: 0.7; }
    .score strong { font-size: 18px; font-variant-numeric: tabular-nums; }
    .wrong { background: #fdecea; color: #8a1c14; border-radius: 6px; padding: 6px 10px; font-size: 13px; margin-bottom: 8px; }
    .wrong ul { margin: 4px 0 0; padding-left: 18px; }
    .card footer { display: flex; flex-wrap: wrap; gap: 4px 14px; margin-top: 10px; padding-top: 8px; border-top: 1px solid var(--mat-sys-outline-variant); font-size: 12px; color: var(--mat-sys-on-surface-variant); }
    .runs { width: 100%; border-collapse: collapse; font-size: 13px; }
    .runs th, .runs td { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--mat-sys-outline-variant); }
    .runs tr.selected { background: var(--mat-sys-secondary-container); }
    .pager { display: flex; align-items: center; gap: 12px; justify-content: flex-end; font-size: 13px; }
  `,
})
export class ComparisonPage {
  private readonly comparison = inject(ComparisonService);
  private readonly demo = inject(DemoService);
  private readonly providers = inject(ProvidersService);
  private readonly auth = inject(AuthService);

  protected readonly min = COMPARISON_MIN_MODELS;
  protected readonly max = COMPARISON_MAX_MODELS;
  protected readonly scoreLabels = SCORE_LABELS;

  protected readonly statuses = signal<ProviderStatus[]>([]);
  protected readonly models = signal<ModelInfo[]>([]);
  protected readonly selected = signal<ReadonlySet<string>>(new Set());
  protected readonly fixedQuestion = signal('');
  protected readonly question = signal('');

  protected readonly busy = signal(false);
  protected readonly loadError = signal<string | null>(null);
  protected readonly runError = signal<string | null>(null);
  protected readonly result = signal<ComparisonRunResponse | null>(null);

  protected readonly history = signal<ComparisonHistoryPage | null>(null);
  protected readonly historyError = signal<string | null>(null);
  private offset = 0;

  protected readonly canRun = computed(() => this.auth.hasPermission(NEEDS_RUN));
  protected readonly enoughModels = computed(() => this.selected().size >= COMPARISON_MIN_MODELS);
  protected readonly canSubmit = computed(() => this.canRun() && !this.busy() && this.enoughModels());
  protected readonly anyCloud = computed(() => this.models().some((m) => m.cloud && this.selected().has(key(m))));

  protected label = labelFromKey;
  protected fmt = formatMetric;

  constructor() {
    this.providers.status().subscribe({
      next: (s) => this.statuses.set(s),
      error: (err: unknown) => this.loadError.set(describeApiError(err)),
    });
    this.providers.models().subscribe({
      next: (m) => this.models.set(m),
      error: (err: unknown) => this.loadError.set(describeApiError(err)),
    });
    this.demo.question().subscribe({
      next: (q) => {
        this.fixedQuestion.set(q);
        if (!this.question()) this.question.set(q);
      },
      error: () => undefined, // optional convenience: the backend defaults to the fixed question anyway
    });
    this.loadHistory();
  }

  protected isSelected(m: ModelInfo): boolean {
    return this.selected().has(key(m));
  }

  protected isConfigured(m: ModelInfo): boolean {
    return this.statuses().find((s) => s.provider === m.provider)?.configured ?? false;
  }

  protected providerLabel(m: ModelInfo): string {
    return this.statuses().find((s) => s.provider === m.provider)?.label ?? m.provider;
  }

  protected reasonFor(m: ModelInfo): string {
    const s = this.statuses().find((x) => x.provider === m.provider);
    return s?.detail || 'This provider is not configured on the backend.';
  }

  protected toggle(m: ModelInfo, checked: boolean): void {
    const next = new Set(this.selected());
    if (checked) next.add(key(m));
    else next.delete(key(m));
    this.selected.set(next);
  }

  protected useFixedQuestion(): void {
    this.question.set(this.fixedQuestion());
  }

  protected run(): void {
    if (!this.canSubmit()) return;
    const selections: ModelSelection[] = this.models()
      .filter((m) => this.selected().has(key(m)))
      .map((m) => ({ provider: m.provider, model: m.model_id }));
    const q = this.question().trim();
    this.runError.set(null);
    this.busy.set(true);
    this.comparison.run(q ? { question: q, selections } : { selections }).subscribe({
      next: (r) => {
        this.busy.set(false);
        this.result.set(r);
        this.loadHistory();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.runError.set(describeApiError(err));
      },
    });
  }

  protected open(id: string): void {
    this.runError.set(null);
    this.comparison.detail(id).subscribe({
      next: (r) => this.result.set(r),
      error: (err: unknown) => this.runError.set(describeApiError(err)),
    });
  }

  protected page(direction: 1 | -1): void {
    this.offset = Math.max(0, this.offset + direction * HISTORY_PAGE);
    this.loadHistory();
  }

  protected metricEntries(r: ComparisonRunResponse): [string, unknown][] {
    return Object.entries(r.shared_context.snapshot_metrics);
  }

  protected statusText(s: ModelResultView['status']): string {
    return s === 'completed' ? 'Completed' : s === 'failed' ? 'Failed' : 'Not configured';
  }

  protected scoreOf(m: ModelResultView, name: (typeof SCORE_LABELS)[number][0]): number | null {
    return m.scores[name]?.score ?? null;
  }

  protected pct(score: number | null): string {
    return score === null ? 'n/a' : `${Math.round(score * 100)}%`;
  }

  /** "avg wait minutes: stated 60, true value 75" for each metric where the answer's numbers disagree with the snapshot. */
  protected wrongNumbers(m: ModelResultView, r: ComparisonRunResponse): string[] {
    const wrong = m.scores.accuracy?.wrong_numbers ?? {};
    return Object.entries(wrong).map(
      ([metric, nums]) =>
        `${labelFromKey(metric)}: stated ${nums.join(', ')}, true value ${formatMetric(r.shared_context.snapshot_metrics[metric])}`,
    );
  }

  protected tokens(m: ModelResultView): string {
    return formatTokens(m.usage);
  }

  protected cost(m: ModelResultView): string {
    return formatCost(m.estimated_cost_usd);
  }

  private loadHistory(): void {
    this.comparison.runs(HISTORY_PAGE, this.offset).subscribe({
      next: (h) => {
        this.history.set(h);
        this.historyError.set(null);
      },
      error: (err: unknown) => this.historyError.set(describeApiError(err)),
    });
  }
}

function key(m: ModelInfo): string {
  return `${m.provider}|${m.model_id}`;
}
