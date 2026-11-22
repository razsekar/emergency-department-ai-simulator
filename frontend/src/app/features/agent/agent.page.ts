import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { Subscription, forkJoin } from 'rxjs';
import { describeApiError } from '../../core/api-error';
import { Permissions } from '../../core/auth/auth.models';
import { AuthService } from '../../core/auth/auth.service';
import { CloudDisclosure } from '../playground/cloud-disclosure.component';
import { ModelPicker } from '../playground/model-picker.component';
import { ModelInfo, ProviderName, ProvidersService, ProviderStatus } from '../playground/providers.service';
import { AgentMode, AgentRunResponse, RunPage, RunTypeFilter } from './agent.models';
import { AgentRunView } from './agent-run-view.component';
import { AgentService } from './agent.service';

const PAGE_SIZE = 10;

@Component({
  selector: 'app-agent-page',
  imports: [
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressBarModule,
    MatSelectModule,
    ModelPicker,
    CloudDisclosure,
    AgentRunView,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1>Agent Execution</h1>
    <p class="lead">
      The agent calls approved backend tools (at most 5 per request), reads their real results, retrieves policy
      excerpts, then the model writes the answer. It performs no clinical actions.
    </p>

    @if (loadError()) {
      <p class="error" role="alert">{{ loadError() }}</p>
    }
    @if (!canRun()) {
      <p class="notice" role="note">
        <mat-icon aria-hidden="true">lock</mat-icon>
        <span>Running the agent needs the “agent:run” permission. Sign in with a presenter or admin account.</span>
      </p>
    }

    <mat-card appearance="outlined">
      <mat-card-content>
        <app-model-picker
          [statuses]="statuses()"
          [models]="models()"
          [(provider)]="provider"
          [(modelId)]="modelId"
          [(temperature)]="temperature"
          [showStreaming]="false"
        />
        <div class="row">
          <mat-form-field appearance="outline" class="mode">
            <mat-label>Tool-calling mode</mat-label>
            <mat-select [ngModel]="mode()" (ngModelChange)="mode.set($event)">
              <mat-option value="auto">Auto (native when the model supports it)</mat-option>
              <mat-option value="native">Native tool calling</mat-option>
              <mat-option value="fallback">Fallback (deterministic tool plan)</mat-option>
            </mat-select>
          </mat-form-field>
          @if (selectedModel(); as m) {
            <span class="support" [attr.data-support]="m.supports_tools">
              Tool-calling support: {{ m.supports_tools === null ? 'unknown' : m.supports_tools ? 'yes' : 'no' }}
            </span>
          }
        </div>
        <app-cloud-disclosure [cloud]="selectedStatus()?.cloud ?? false" [text]="selectedStatus()?.data_disclosure ?? null" />
      </mat-card-content>
    </mat-card>

    <form class="ask" (submit)="$event.preventDefault(); run()">
      <mat-form-field appearance="outline" class="grow">
        <mat-label>Question for the agent</mat-label>
        <textarea matInput rows="4" name="question" [ngModel]="question()" (ngModelChange)="question.set($event)"></textarea>
        <mat-hint>{{ question().length }}/2000</mat-hint>
      </mat-form-field>
      <div class="actions">
        <button mat-stroked-button type="button" (click)="useDemoQuestion()" [disabled]="busy()">
          <mat-icon>bolt</mat-icon> Use the fixed demonstration question
        </button>
        <button mat-flat-button type="submit" [disabled]="!canSubmit()">
          <mat-icon>smart_toy</mat-icon> {{ busy() ? 'Agent running…' : 'Run agent' }}
        </button>
        @if (busy()) {
          <button mat-button type="button" (click)="cancel()">Cancel</button>
        }
      </div>
    </form>
    @if (busy()) {
      <mat-progress-bar mode="indeterminate" aria-label="Agent running" />
      <p class="muted">Each run fetches fresh data and may take a minute: the model is called once per tool round plus once for the answer.</p>
    }
    @if (runError()) {
      <p class="error" role="alert">{{ runError() }}</p>
    }

    @if (current(); as r) {
      <mat-card appearance="outlined" class="result">
        <mat-card-header><mat-card-title>Result</mat-card-title></mat-card-header>
        <mat-card-content><app-agent-run-view [run]="r" /></mat-card-content>
      </mat-card>
    }

    <mat-card appearance="outlined" class="history">
      <mat-card-header><mat-card-title>Execution history</mat-card-title></mat-card-header>
      <mat-card-content>
        <div class="row">
          <mat-form-field appearance="outline" class="filter">
            <mat-label>Run type</mat-label>
            <mat-select [ngModel]="runType()" (ngModelChange)="changeFilter($event)">
              <mat-option value="all">All</mat-option>
              <mat-option value="agent">Agent runs</mat-option>
              <mat-option value="demo">Demo runs</mat-option>
            </mat-select>
          </mat-form-field>
          <button mat-button type="button" (click)="loadHistory()"><mat-icon>refresh</mat-icon> Refresh</button>
        </div>
        @if (historyError()) {
          <p class="error" role="alert">{{ historyError() }}</p>
        }
        @if (history(); as h) {
          @if (h.items.length === 0) {
            <p class="muted">No runs recorded yet.</p>
          } @else {
            <div class="scroll">
              <table class="runs">
                <thead>
                  <tr>
                    <th>When</th><th>Scenario</th><th>Model</th><th>Mode</th><th>Tools</th><th>Latency</th><th>Status</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  @for (s of h.items; track s.id) {
                    <tr [class.selected]="s.id === selectedId()">
                      <td>{{ s.created_at }}</td>
                      <td>{{ s.scenario_name ?? '—' }} <span class="muted">v{{ s.data_version ?? '?' }}</span></td>
                      <td>{{ s.provider }} / {{ s.model }}</td>
                      <td>{{ s.mode }}{{ s.run_type === 'demo' ? ' · demo' : '' }}</td>
                      <td [title]="s.tool_names.join(', ')">{{ s.tool_names.length }}</td>
                      <td>{{ s.latency_ms }} ms</td>
                      <td>{{ s.status }}</td>
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
    :host { display: block; max-width: 1100px; }
    h1 { margin: 0 0 4px; }
    .lead { margin: 0 0 12px; color: var(--mat-sys-on-surface-variant); }
    mat-card { margin-bottom: 16px; }
    .row { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; }
    .mode { min-width: 300px; }
    .filter { min-width: 160px; }
    .support { font-size: 13px; }
    .support[data-support='false'] { color: #b45309; }
    .ask { display: flex; gap: 12px; align-items: flex-start; flex-wrap: wrap; margin: 16px 0 8px; }
    .grow { flex: 1 1 420px; }
    .actions { display: flex; flex-direction: column; gap: 8px; }
    .notice { display: flex; gap: 8px; align-items: center; padding: 8px 12px; border-radius: 8px; background: #e8eef7; color: #1f3a5f; font-size: 13px; }
    .muted { color: var(--mat-sys-on-surface-variant); font-size: 13px; }
    .error { color: #b3261e; }
    .scroll { overflow-x: auto; }
    .runs { width: 100%; border-collapse: collapse; font-size: 13px; }
    .runs th, .runs td { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--mat-sys-outline-variant); white-space: nowrap; }
    .runs tr.selected { background: var(--mat-sys-secondary-container); }
    .pager { display: flex; align-items: center; gap: 12px; justify-content: flex-end; font-size: 13px; }
  `,
})
export class AgentPage {
  private readonly agent = inject(AgentService);
  private readonly providers = inject(ProvidersService);
  private readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly statuses = signal<ProviderStatus[]>([]);
  protected readonly models = signal<ModelInfo[]>([]);
  protected readonly provider = signal<ProviderName | null>(null);
  protected readonly modelId = signal<string | null>(null);
  protected readonly temperature = signal(0.2);
  protected readonly mode = signal<AgentMode>('auto');
  protected readonly question = signal('');

  protected readonly busy = signal(false);
  protected readonly loadError = signal<string | null>(null);
  protected readonly runError = signal<string | null>(null);
  protected readonly current = signal<AgentRunResponse | null>(null);
  protected readonly selectedId = computed(() => this.current()?.id ?? null);

  protected readonly history = signal<RunPage | null>(null);
  protected readonly historyError = signal<string | null>(null);
  protected readonly runType = signal<RunTypeFilter>('all');
  private offset = 0;
  private runSub: Subscription | null = null;

  protected readonly selectedStatus = computed(() => this.statuses().find((s) => s.provider === this.provider()) ?? null);
  protected readonly selectedModel = computed(
    () => this.models().find((m) => m.provider === this.provider() && m.model_id === this.modelId()) ?? null,
  );
  protected readonly canRun = computed(() => this.auth.hasPermission(Permissions.AgentRun));
  protected readonly canSubmit = computed(
    () => this.canRun() && !this.busy() && !!this.selectedModel() && this.question().trim().length >= 3,
  );

  constructor() {
    forkJoin({ statuses: this.providers.status(), models: this.providers.models() })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ statuses, models }) => {
          this.statuses.set(statuses);
          this.models.set(models);
        },
        error: (err: unknown) => this.loadError.set(describeApiError(err)),
      });
    this.loadHistory();
  }

  protected useDemoQuestion(): void {
    this.agent
      .demoQuestion()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (q) => this.question.set(q),
        error: (err: unknown) => this.runError.set(describeApiError(err)),
      });
  }

  protected run(): void {
    const model = this.selectedModel();
    if (!model || !this.canSubmit()) return;
    this.busy.set(true);
    this.runError.set(null);
    this.runSub = this.agent
      .run({
        question: this.question().trim(),
        provider: model.provider,
        model: model.model_id,
        temperature: this.temperature(),
        mode: this.mode(),
      })
      .subscribe({
        next: (res) => {
          this.current.set(res);
          this.busy.set(false);
          this.offset = 0;
          this.loadHistory();
        },
        error: (err: unknown) => {
          this.runError.set(describeApiError(err));
          this.busy.set(false);
        },
      });
  }

  protected cancel(): void {
    this.runSub?.unsubscribe(); // aborts the HTTP request; the backend may still finish and record the run
    this.runSub = null;
    this.busy.set(false);
    this.runError.set('Cancelled in the browser. The server may still complete and record the run.');
  }

  protected changeFilter(value: RunTypeFilter): void {
    this.runType.set(value);
    this.offset = 0;
    this.loadHistory();
  }

  protected page(direction: 1 | -1): void {
    this.offset = Math.max(0, this.offset + direction * PAGE_SIZE);
    this.loadHistory();
  }

  protected loadHistory(): void {
    this.historyError.set(null);
    this.agent
      .runs(PAGE_SIZE, this.offset, this.runType())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (p) => this.history.set(p),
        error: (err: unknown) => this.historyError.set(describeApiError(err)),
      });
  }

  protected open(id: string): void {
    this.runError.set(null);
    this.agent
      .runDetail(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (r) => this.current.set(r),
        error: (err: unknown) => this.runError.set(describeApiError(err)),
      });
  }
}
