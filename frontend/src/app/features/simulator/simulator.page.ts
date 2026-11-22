import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { Observable } from 'rxjs';
import {
  ApplyResponse,
  DEPARTMENT_CODES,
  ScenarioInfo,
  ScenarioKey,
  ScenarioOverrides,
  ScenarioParams,
  ScenarioRunInfo,
} from './simulator.models';
import { ScenarioService, apiErrorMessage } from './simulator.service';

type BaseKey = Exclude<ScenarioKey, 'custom'>;

interface FieldDef {
  name: Exclude<keyof ScenarioParams, 'department_workload'>;
  label: string;
  min: number;
  max: number;
  step: number;
  hint?: string;
}

const FIELDS: FieldDef[] = [
  { name: 'arrival_rate_per_hour', label: 'Patient arrival rate (per hour)', min: 0, max: 200, step: 0.5 },
  { name: 'beds_available', label: 'Available beds', min: 0, max: 100, step: 1 },
  { name: 'beds_occupied', label: 'Occupied beds', min: 0, max: 100, step: 1 },
  { name: 'doctors_on_duty', label: 'Doctors on duty', min: 0, max: 100, step: 1 },
  { name: 'nurses_on_duty', label: 'Nurses on duty', min: 0, max: 200, step: 1 },
  { name: 'waiting_patients', label: 'Pending (waiting) patients', min: 0, max: 300, step: 1 },
  { name: 'avg_wait_minutes', label: 'Mean patient waiting time (min)', min: 1, max: 240, step: 1 },
  { name: 'pending_investigations', label: 'Pending investigations', min: 0, max: 300, step: 1 },
  {
    name: 'investigation_delay_minutes',
    label: 'Investigation delay (min)',
    min: 1,
    max: 240,
    step: 1,
    hint: 'Mean age of pending requests',
  },
  { name: 'window_minutes', label: 'Analysis time window (min)', min: 60, max: 1440, step: 10, hint: '≥ 1.8 × mean wait' },
  { name: 'seed', label: 'Random seed', min: 0, max: 2147483647, step: 1, hint: 'Same seed = same records' },
];

@Component({
  selector: 'app-simulator-page',
  imports: [
    DatePipe,
    ReactiveFormsModule,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressBarModule,
    MatSelectModule,
    MatTableModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1>Scenario Simulator</h1>

    <mat-card appearance="outlined" class="current" [attr.data-scenario]="scenario.state()?.scenario_key ?? 'none'">
      <mat-card-content>
        <div class="current-row">
          <div>
            <div class="eyebrow">Current scenario (from database)</div>
            <div class="current-name">{{ scenario.state()?.scenario_name ?? 'No scenario loaded' }}</div>
          </div>
          <div class="version">
            <div class="eyebrow">Data version</div>
            <div class="current-name">v{{ scenario.state()?.data_version ?? '—' }}</div>
          </div>
          <div>
            <div class="eyebrow">Applied</div>
            <div>{{ scenario.state()?.applied_at ? (scenario.state()!.applied_at | date: 'medium') : '—' }}</div>
          </div>
        </div>
      </mat-card-content>
    </mat-card>

    @if (busy()) {
      <mat-progress-bar mode="indeterminate" aria-label="Applying scenario" />
    }

    <mat-card appearance="outlined" class="panel">
      <mat-card-header>
        <mat-card-title>Control panel</mat-card-title>
        <mat-card-subtitle>
          Every action rewrites the PostgreSQL records in one transaction and increments the data version.
        </mat-card-subtitle>
      </mat-card-header>
      <mat-card-content>
        <div class="actions">
          <button mat-flat-button data-test="load-normal" [disabled]="busy()" (click)="load('normal')">
            <mat-icon>check_circle</mat-icon> Load Baseline
          </button>
          <button mat-flat-button class="surge" data-test="load-surge" [disabled]="busy()" (click)="load('surge')">
            <mat-icon>warning</mat-icon> Load Emergency Surge
          </button>
          <button mat-flat-button data-test="load-recovery" [disabled]="busy()" (click)="load('recovery')">
            <mat-icon>healing</mat-icon> Load Recovery
          </button>
          <button mat-stroked-button data-test="randomize" [disabled]="busy()" (click)="randomize()">
            <mat-icon>casino</mat-icon> Randomize Scenario
          </button>
          <button mat-stroked-button data-test="reset" [disabled]="busy()" (click)="reset()">
            <mat-icon>restart_alt</mat-icon> Reset Database
          </button>
        </div>
        @if (message(); as m) {
          <p class="msg" [class.error]="m.kind === 'error'" role="status">{{ m.text }}</p>
        }
        @if (last(); as r) {
          <p class="last">
            Last run: <strong>{{ r.run.scenario_name }}</strong> · {{ r.run.status }} ·
            data v{{ r.run.data_version }} · {{ r.run.record_count }} records · {{ r.run.duration_ms }} ms
          </p>
        }
      </mat-card-content>
    </mat-card>

    <mat-card appearance="outlined" class="panel">
      <mat-card-header>
        <mat-card-title>Manual parameter editor</mat-card-title>
        <mat-card-subtitle>
          Start from a base scenario, change values, then Apply. Individual records are regenerated from these
          parameters; the dashboard numbers are calculated from them, not typed in.
        </mat-card-subtitle>
      </mat-card-header>
      <mat-card-content>
        <form [formGroup]="form" (ngSubmit)="applyManual()" class="editor">
          <mat-form-field appearance="outline" class="base">
            <mat-label>Base scenario</mat-label>
            <mat-select [value]="base()" (selectionChange)="selectBase($event.value)" data-test="base">
              @for (s of scenarios(); track s.key) {
                <mat-option [value]="s.key">{{ s.name }}</mat-option>
              }
            </mat-select>
          </mat-form-field>

          <div class="grid">
            @for (f of fields; track f.name) {
              <mat-form-field appearance="outline">
                <mat-label>{{ f.label }}</mat-label>
                <input matInput type="number" [formControlName]="f.name" [attr.data-field]="f.name" [min]="f.min" [max]="f.max" [step]="f.step" />
                @if (f.hint) {
                  <mat-hint>{{ f.hint }}</mat-hint>
                }
                @if (form.controls[f.name].invalid) {
                  <mat-error>Enter a number from {{ f.min }} to {{ f.max }}</mat-error>
                }
              </mat-form-field>
            }
          </div>

          <h3>Department workload weights</h3>
          <div class="grid" formGroupName="department_workload">
            @for (code of departments; track code) {
              <mat-form-field appearance="outline">
                <mat-label>{{ code }}</mat-label>
                <input matInput type="number" [formControlName]="code" min="0" max="1" step="0.05" />
                <mat-hint>Relative share; normalised on apply</mat-hint>
              </mat-form-field>
            }
          </div>

          <div class="actions">
            <button mat-flat-button type="submit" data-test="apply" [disabled]="busy() || form.invalid">
              <mat-icon>publish</mat-icon> Apply Scenario
            </button>
            <button mat-button type="button" [disabled]="busy()" (click)="selectBase(base())">Revert edits</button>
          </div>
        </form>
      </mat-card-content>
    </mat-card>

    <mat-card appearance="outlined" class="panel">
      <mat-card-header>
        <mat-card-title>Scenario history</mat-card-title>
        <mat-card-subtitle>{{ historyTotal() }} runs recorded (newest first)</mat-card-subtitle>
      </mat-card-header>
      <mat-card-content>
        <div class="table-wrap">
          <table mat-table [dataSource]="history()" aria-label="Scenario history">
            <ng-container matColumnDef="when">
              <th mat-header-cell *matHeaderCellDef>When</th>
              <td mat-cell *matCellDef="let r">{{ r.created_at | date: 'medium' }}</td>
            </ng-container>
            <ng-container matColumnDef="scenario">
              <th mat-header-cell *matHeaderCellDef>Scenario</th>
              <td mat-cell *matCellDef="let r">{{ r.scenario_name }}</td>
            </ng-container>
            <ng-container matColumnDef="trigger">
              <th mat-header-cell *matHeaderCellDef>Trigger</th>
              <td mat-cell *matCellDef="let r">{{ r.trigger }}</td>
            </ng-container>
            <ng-container matColumnDef="status">
              <th mat-header-cell *matHeaderCellDef>Status</th>
              <td mat-cell *matCellDef="let r" [class.failed]="r.status !== 'success' && r.status !== 'applied'">
                {{ r.status }}
              </td>
            </ng-container>
            <ng-container matColumnDef="version">
              <th mat-header-cell *matHeaderCellDef>Data version</th>
              <td mat-cell *matCellDef="let r">{{ r.data_version ?? '—' }}</td>
            </ng-container>
            <ng-container matColumnDef="records">
              <th mat-header-cell *matHeaderCellDef>Records</th>
              <td mat-cell *matCellDef="let r">{{ r.record_count }}</td>
            </ng-container>
            <ng-container matColumnDef="duration">
              <th mat-header-cell *matHeaderCellDef>Duration</th>
              <td mat-cell *matCellDef="let r">{{ r.duration_ms }} ms</td>
            </ng-container>
            <tr mat-header-row *matHeaderRowDef="columns"></tr>
            <tr mat-row *matRowDef="let row; columns: columns"></tr>
            <tr class="mat-row" *matNoDataRow>
              <td class="mat-cell" [attr.colspan]="columns.length">No scenario has been applied yet.</td>
            </tr>
          </table>
        </div>
      </mat-card-content>
    </mat-card>
  `,
  styles: `
    h1 { margin: 0 0 16px; font-weight: 500; }
    .current { margin-bottom: 16px; border-width: 2px; }
    .current[data-scenario='surge'] { border-color: #b91c1c; background: #fef2f2; }
    .current[data-scenario='normal'] { border-color: #15803d; }
    .current[data-scenario='recovery'] { border-color: #0369a1; }
    .current[data-scenario='custom'] { border-color: #7e22ce; }
    .current-row { display: flex; gap: 40px; flex-wrap: wrap; align-items: flex-end; }
    .eyebrow { font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.7; }
    .current-name { font-size: 26px; font-weight: 500; }
    .panel { margin: 16px 0; }
    mat-card-content { padding-top: 16px; }
    .actions { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
    .actions .surge { --mat-button-filled-container-color: #b91c1c; --mat-button-filled-label-text-color: #fff; }
    .msg { margin: 12px 0 0; font-weight: 500; color: var(--ed-ok); }
    .msg.error { color: var(--ed-down); }
    .last { margin: 8px 0 0; opacity: 0.8; font-size: 14px; }
    .editor .base { width: 100%; max-width: 360px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 0 16px; }
    h3 { margin: 8px 0; font-weight: 500; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; }
    .failed { color: var(--ed-down); font-weight: 500; }
  `,
})
export class SimulatorPage {
  protected readonly scenario = inject(ScenarioService);
  private readonly fb = inject(FormBuilder);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly fields = FIELDS;
  protected readonly departments = DEPARTMENT_CODES;
  protected readonly columns = ['when', 'scenario', 'trigger', 'status', 'version', 'records', 'duration'];

  protected readonly scenarios = signal<ScenarioInfo[]>([]);
  protected readonly base = signal<BaseKey>('normal');
  protected readonly busy = signal(false);
  protected readonly message = signal<{ kind: 'ok' | 'error'; text: string } | null>(null);
  protected readonly last = signal<ApplyResponse | null>(null);
  protected readonly history = signal<ScenarioRunInfo[]>([]);
  protected readonly historyTotal = signal(0);

  protected readonly form = this.fb.nonNullable.group({
    seed: [0, [Validators.required, Validators.min(0), Validators.max(2147483647)]],
    arrival_rate_per_hour: [0, [Validators.required, Validators.min(0), Validators.max(200)]],
    beds_available: [0, [Validators.required, Validators.min(0), Validators.max(100)]],
    beds_occupied: [0, [Validators.required, Validators.min(0), Validators.max(100)]],
    doctors_on_duty: [0, [Validators.required, Validators.min(0), Validators.max(100)]],
    nurses_on_duty: [0, [Validators.required, Validators.min(0), Validators.max(200)]],
    waiting_patients: [0, [Validators.required, Validators.min(0), Validators.max(300)]],
    avg_wait_minutes: [1, [Validators.required, Validators.min(1), Validators.max(240)]],
    pending_investigations: [0, [Validators.required, Validators.min(0), Validators.max(300)]],
    investigation_delay_minutes: [1, [Validators.required, Validators.min(1), Validators.max(240)]],
    window_minutes: [60, [Validators.required, Validators.min(60), Validators.max(1440)]],
    department_workload: this.fb.nonNullable.group({
      ACUTE: [0, [Validators.required, Validators.min(0)]],
      RESUS: [0, [Validators.required, Validators.min(0)]],
      MINOR: [0, [Validators.required, Validators.min(0)]],
      PEDS: [0, [Validators.required, Validators.min(0)]],
    }),
  });

  constructor() {
    this.scenario.refreshState().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({ error: () => undefined });
    this.scenario
      .list()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (list) => {
          this.scenarios.set(list);
          this.selectBase('normal');
        },
        error: (e) => this.message.set({ kind: 'error', text: apiErrorMessage(e) }),
      });
    this.loadHistory();
  }

  protected selectBase(key: string): void {
    const info = this.scenarios().find((s) => s.key === key);
    if (!info) return;
    this.base.set(key as BaseKey);
    this.form.reset(this.toFormValue(info.parameters));
  }

  protected load(key: BaseKey): void {
    this.run(this.scenario.apply(key), 'Scenario loaded.');
  }

  protected randomize(): void {
    this.run(this.scenario.randomize(), 'Randomized scenario applied.');
  }

  protected reset(): void {
    this.run(this.scenario.reset(), 'Database reset.');
  }

  protected applyManual(): void {
    if (this.form.invalid) return;
    const overrides = this.changedFields();
    const key = this.base();
    this.run(
      Object.keys(overrides).length ? this.scenario.apply(key, overrides) : this.scenario.apply(key),
      Object.keys(overrides).length ? 'Custom scenario applied.' : 'No edits: base scenario applied.',
    );
  }

  /** Only the fields that differ from the selected base scenario are sent as overrides. */
  private changedFields(): ScenarioOverrides {
    const info = this.scenarios().find((s) => s.key === this.base());
    if (!info) return {};
    const value = this.form.getRawValue();
    const out: Record<string, unknown> = {};
    for (const f of FIELDS) {
      if (value[f.name] !== info.parameters[f.name]) out[f.name] = value[f.name];
    }
    const base = info.parameters.department_workload;
    if (DEPARTMENT_CODES.some((c) => value.department_workload[c] !== (base[c] ?? 0))) {
      out['department_workload'] = { ...value.department_workload };
    }
    return out as ScenarioOverrides;
  }

  private toFormValue(p: ScenarioParams) {
    return {
      seed: p.seed,
      arrival_rate_per_hour: p.arrival_rate_per_hour,
      beds_available: p.beds_available,
      beds_occupied: p.beds_occupied,
      doctors_on_duty: p.doctors_on_duty,
      nurses_on_duty: p.nurses_on_duty,
      waiting_patients: p.waiting_patients,
      avg_wait_minutes: p.avg_wait_minutes,
      pending_investigations: p.pending_investigations,
      investigation_delay_minutes: p.investigation_delay_minutes,
      window_minutes: p.window_minutes,
      department_workload: {
        ACUTE: p.department_workload['ACUTE'] ?? 0,
        RESUS: p.department_workload['RESUS'] ?? 0,
        MINOR: p.department_workload['MINOR'] ?? 0,
        PEDS: p.department_workload['PEDS'] ?? 0,
      },
    };
  }

  private run(call: Observable<ApplyResponse>, okText: string): void {
    this.busy.set(true);
    this.message.set(null);
    call.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (r) => {
        this.busy.set(false);
        this.last.set(r);
        this.message.set({ kind: 'ok', text: `${okText} Data version is now v${r.state.data_version}.` });
        this.loadHistory();
        this.refreshScenarioList();
      },
      error: (e) => {
        this.busy.set(false);
        this.message.set({ kind: 'error', text: `Not applied (database unchanged): ${apiErrorMessage(e)}` });
        this.loadHistory();
      },
    });
  }

  private refreshScenarioList(): void {
    this.scenario
      .list()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({ next: (list) => this.scenarios.set(list), error: () => undefined });
  }

  private loadHistory(): void {
    this.scenario
      .history(10)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (p) => {
          this.history.set(p.items);
          this.historyTotal.set(p.total);
        },
        error: () => undefined,
      });
  }
}
