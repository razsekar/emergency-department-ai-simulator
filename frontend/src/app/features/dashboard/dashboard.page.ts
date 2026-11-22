import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { RouterLink } from '@angular/router';
import { ScenarioService, apiErrorMessage } from '../simulator/simulator.service';
import { BarChartComponent, BarDatum } from './bar-chart.component';
import { DashboardMetrics } from './dashboard.models';
import { DashboardService, bucketForWindow } from './dashboard.service';

interface Tile {
  key: string;
  label: string;
  value: string;
  sub?: string;
  tone?: 'critical';
}

export const WINDOW_OPTIONS = [
  { minutes: 60, label: 'Last 1 hour' },
  { minutes: 120, label: 'Last 2 hours' },
  { minutes: 240, label: 'Last 4 hours' },
  { minutes: 480, label: 'Last 8 hours' },
  { minutes: 1440, label: 'Last 24 hours' },
];

@Component({
  selector: 'app-dashboard-page',
  imports: [
    DatePipe,
    DecimalPipe,
    RouterLink,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatIconModule,
    MatProgressBarModule,
    MatSelectModule,
    BarChartComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="head">
      <h1>Operations Dashboard</h1>
      <span class="spacer"></span>
      <mat-form-field appearance="outline" subscriptSizing="dynamic" class="win">
        <mat-label>Analysis window</mat-label>
        <mat-select [value]="windowMinutes()" (selectionChange)="windowMinutes.set($event.value)">
          @for (o of windowOptions; track o.minutes) {
            <mat-option [value]="o.minutes">{{ o.label }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <button mat-stroked-button (click)="load()" [disabled]="loading()" data-test="refresh">
        <mat-icon>refresh</mat-icon> Refresh
      </button>
    </div>

    @if (loading()) {
      <mat-progress-bar mode="indeterminate" />
    }

    @if (error(); as e) {
      <mat-card appearance="outlined" class="notice error" role="alert">
        <mat-card-content>Could not load metrics: {{ e }}</mat-card-content>
      </mat-card>
    }

    @if (m(); as d) {
      <p class="meta" data-test="meta">
        <strong>{{ d.scenario_name ?? 'No scenario loaded' }}</strong>
        · data v{{ d.data_version }}
        @if (d.as_of) {
          · as of {{ d.as_of | date: 'medium' }}
        }
        · calculated from database records · synthetic data
      </p>

      @if (d.data_version === 0 || d.total_visits === 0) {
        <mat-card appearance="outlined" class="notice">
          <mat-card-content>
            The database has no patient records yet.
            <a routerLink="/simulator">Load a scenario in the Scenario Simulator</a> to generate them.
          </mat-card-content>
        </mat-card>
      }

      <section class="tiles" aria-label="Key metrics">
        @for (t of tiles(); track t.key) {
          <mat-card appearance="outlined" class="tile" [class.critical]="t.tone === 'critical'" [attr.data-tile]="t.key">
            <mat-card-content>
              <div class="label">{{ t.label }}</div>
              <div class="value">{{ t.value }}</div>
              @if (t.sub) {
                <div class="sub">{{ t.sub }}</div>
              }
            </mat-card-content>
          </mat-card>
        }
      </section>

      <section class="charts">
        <mat-card appearance="outlined">
          <mat-card-header><mat-card-title>Patient arrivals over time</mat-card-title>
            <mat-card-subtitle>Arrivals per {{ bucket() }} min bucket</mat-card-subtitle></mat-card-header>
          <mat-card-content>
            <app-bar-chart [data]="arrivals()" color="#0369a1" ariaLabel="Patient arrivals over time" />
          </mat-card-content>
        </mat-card>

        <mat-card appearance="outlined">
          <mat-card-header><mat-card-title>Waiting-time distribution</mat-card-title>
            <mat-card-subtitle>Patients currently waiting, by minutes waited</mat-card-subtitle></mat-card-header>
          <mat-card-content>
            <app-bar-chart [data]="distribution()" color="#b45309" ariaLabel="Waiting-time distribution" />
          </mat-card-content>
        </mat-card>

        <mat-card appearance="outlined">
          <mat-card-header><mat-card-title>Department workload</mat-card-title>
            <mat-card-subtitle>Active patients by department</mat-card-subtitle></mat-card-header>
          <mat-card-content>
            <div class="legend">
              <span><i class="sw waiting"></i>Waiting</span>
              <span><i class="sw treat"></i>In treatment</span>
              <span><i class="sw inv"></i>Pending investigations</span>
            </div>
            @for (w of d.department_workload; track w.department_code) {
              <div class="wl" [attr.data-dept]="w.department_code">
                <div class="wl-name">{{ w.department_code }} <small>{{ w.total_active }} active</small></div>
                <div class="wl-bars">
                  <div class="bar waiting" [style.width.%]="pct(w.waiting, maxWorkload())"></div>
                  <div class="bar treat" [style.width.%]="pct(w.in_treatment, maxWorkload())"></div>
                  <div class="bar inv" [style.width.%]="pct(w.pending_investigations, maxWorkload())"></div>
                </div>
                <div class="wl-nums">{{ w.waiting }} / {{ w.in_treatment }} / {{ w.pending_investigations }}</div>
              </div>
            } @empty {
              <p class="empty">No department data.</p>
            }
          </mat-card-content>
        </mat-card>

        <mat-card appearance="outlined">
          <mat-card-header><mat-card-title>Resource utilization</mat-card-title>
            <mat-card-subtitle>Calculated from beds, staff and requests</mat-card-subtitle></mat-card-header>
          <mat-card-content>
            @for (r of meters(); track r.label) {
              <div class="meter" [attr.data-meter]="r.label">
                <div class="meter-row"><span>{{ r.label }}</span><span>{{ r.value | number: '1.0-1' }}%</span></div>
                <div class="track"><div class="fill" [style.width.%]="r.fill"></div></div>
                @if (r.sub) {
                  <small>{{ r.sub }}</small>
                }
              </div>
            }
          </mat-card-content>
        </mat-card>
      </section>
    }
  `,
  styles: `
    .head { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
    h1 { margin: 0; font-weight: 500; }
    .spacer { flex: 1; }
    .win { width: 190px; }
    .meta { margin: 8px 0 16px; opacity: 0.85; }
    .notice { margin: 0 0 16px; border-color: #b45309; }
    .notice.error { border-color: var(--ed-down); color: var(--ed-down); }
    .tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 12px; margin-bottom: 20px; }
    .tile .label { font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; opacity: 0.75; min-height: 2.4em; }
    .tile .value { font-size: 32px; font-weight: 500; font-variant-numeric: tabular-nums; }
    .tile .sub { font-size: 12px; opacity: 0.7; }
    .tile.critical { border-color: #b91c1c; }
    .tile.critical .value { color: #b91c1c; }
    .charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; }
    mat-card-content { padding-top: 12px; }
    .legend { display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px; margin-bottom: 8px; }
    .sw { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; }
    .waiting { background: #b45309; } .treat { background: #0369a1; } .inv { background: #7e22ce; }
    .wl { display: grid; grid-template-columns: 110px 1fr 90px; gap: 8px; align-items: center; margin: 8px 0; }
    .wl-name small { display: block; opacity: 0.7; }
    .wl-bars { display: flex; flex-direction: column; gap: 2px; }
    .bar { height: 7px; border-radius: 2px; min-width: 2px; }
    .wl-nums { font-size: 12px; text-align: right; font-variant-numeric: tabular-nums; }
    .meter { margin-bottom: 14px; }
    .meter-row { display: flex; justify-content: space-between; font-size: 14px; }
    .track { height: 10px; border-radius: 5px; background: var(--mat-sys-surface-container-highest); overflow: hidden; margin: 4px 0; }
    .fill { height: 100%; background: #0369a1; }
    small { opacity: 0.7; }
    .empty { opacity: 0.7; }
  `,
})
export class DashboardPage {
  private readonly api = inject(DashboardService);
  private readonly scenario = inject(ScenarioService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly windowOptions = WINDOW_OPTIONS;
  protected readonly windowMinutes = signal(240);
  protected readonly bucket = computed(() => bucketForWindow(this.windowMinutes()));
  protected readonly m = signal<DashboardMetrics | null>(null);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly tiles = computed<Tile[]>(() => {
    const d = this.m();
    if (!d) return [];
    const staff = (role: string) => d.staff.find((s) => s.role === role);
    const doc = staff('doctor');
    const nur = staff('nurse');
    return [
      { key: 'total-visits', label: 'Total patient visits', value: `${d.total_visits}` },
      { key: 'waiting', label: 'Patients waiting', value: `${d.patients_waiting}` },
      { key: 'in-treatment', label: 'Currently being attended', value: `${d.patients_in_treatment}` },
      { key: 'beds-available', label: 'Available beds', value: `${d.beds.available}`, sub: `of ${d.beds.total} total` },
      { key: 'beds-occupied', label: 'Occupied beds', value: `${d.beds.occupied}`, sub: `${d.beds.utilization_pct.toFixed(0)}% utilization` },
      { key: 'avg-wait', label: 'Average waiting time', value: `${d.avg_wait_minutes.toFixed(1)} min`, sub: `max ${d.max_wait_minutes.toFixed(1)} min` },
      { key: 'critical', label: 'Critical-category patients', value: `${d.critical_patients}`, tone: 'critical' },
      {
        key: 'pending-investigations',
        label: 'Pending investigations',
        value: `${d.pending_investigations}`,
        sub: `avg age ${d.avg_pending_investigation_age_minutes.toFixed(0)} min`,
      },
      { key: 'discharges', label: 'Completed discharges', value: `${d.completed_discharges}` },
      { key: 'doctors', label: 'Doctors available', value: `${doc?.available ?? 0}`, sub: `of ${doc?.on_duty ?? 0} on duty` },
      { key: 'nurses', label: 'Nurses available', value: `${nur?.available ?? 0}`, sub: `of ${nur?.on_duty ?? 0} on duty` },
    ];
  });

  protected readonly arrivals = computed<BarDatum[]>(() =>
    (this.m()?.arrivals_over_time ?? []).map((a) => ({
      label: new Date(a.bucket_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      value: a.count,
    })),
  );

  protected readonly distribution = computed<BarDatum[]>(() =>
    (this.m()?.waiting_time_distribution ?? []).map((b) => ({ label: b.label, value: b.count })),
  );

  protected readonly maxWorkload = computed(() =>
    Math.max(1, ...(this.m()?.department_workload ?? []).flatMap((w) => [w.waiting, w.in_treatment, w.pending_investigations])),
  );

  protected readonly meters = computed(() => {
    const u = this.m()?.resource_utilization;
    if (!u) return [];
    const base = [
      { label: 'Beds', value: u.beds_pct, sub: undefined as string | undefined },
      { label: 'Doctors', value: u.doctors_pct, sub: undefined },
      { label: 'Nurses', value: u.nurses_pct, sub: undefined },
    ];
    const fac = u.facilities.map((f) => ({
      label: `${f.name} (investigations)`,
      value: f.capacity ? Math.min(100, (f.pending_requests / f.capacity) * 100) : 0,
      sub: `${f.pending_requests} pending · capacity ${f.capacity} · avg age ${f.avg_age_minutes.toFixed(0)} min`,
    }));
    return [...base, ...fac].map((r) => ({ ...r, fill: Math.min(100, Math.max(0, r.value)) }));
  });

  constructor() {
    this.scenario.refreshState().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      error: (e) => this.error.set(apiErrorMessage(e)),
    });
    // Reload whenever the scenario data version changes (applied here, in the simulator, or elsewhere)
    // or the analysis window changes. Metrics are never reused across versions.
    effect(() => {
      const version = this.scenario.dataVersion();
      this.windowMinutes();
      if (version === null) return;
      untracked(() => this.load());
    });
  }

  protected load(): void {
    this.loading.set(true);
    this.api
      .metrics(this.windowMinutes(), this.bucket())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (d) => {
          this.m.set(d);
          this.error.set(null);
          this.loading.set(false);
        },
        error: (e) => {
          this.error.set(apiErrorMessage(e));
          this.loading.set(false);
        },
      });
  }

  protected pct(v: number, max: number): number {
    return (v / max) * 100;
  }
}
