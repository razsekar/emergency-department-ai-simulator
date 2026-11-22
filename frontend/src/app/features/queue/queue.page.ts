import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, effect, inject, signal, untracked } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatSelectModule } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { MatTabsModule } from '@angular/material/tabs';
import { DepartmentCapacity } from '../resources/resources.models';
import { ResourceService } from '../resources/resources.service';
import { ScenarioService, apiErrorMessage } from '../simulator/simulator.service';
import { PendingInvestigations, QueueQuery, QueueRow } from './queue.models';
import { QueueService } from './queue.service';

export function formatWait(minutes: number): string {
  if (minutes < 60) return `${minutes.toFixed(0)} min`;
  const h = Math.floor(minutes / 60);
  return `${h} h ${Math.round(minutes - h * 60)} min`;
}

@Component({
  selector: 'app-queue-page',
  imports: [
    DatePipe,
    DecimalPipe,
    ReactiveFormsModule,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatPaginatorModule,
    MatSelectModule,
    MatTableModule,
    MatTabsModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1>Patient Queue</h1>
    <p class="meta">
      Synthetic patient visits (SIM-PAT-…).
      @if (scenario.state(); as s) {
        {{ s.scenario_name ?? 'No scenario' }} · data v{{ s.data_version }}.
      }
      Simulated triage categories demonstrate data handling only; they are not clinical priorities.
    </p>
    @if (error(); as e) {
      <mat-card appearance="outlined" class="error" role="alert"><mat-card-content>{{ e }}</mat-card-content></mat-card>
    }

    <mat-tab-group animationDuration="0ms" dynamicHeight>
      <mat-tab label="Visits">
        <form class="filters" [formGroup]="filters" (ngSubmit)="search()">
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Status</mat-label>
            <mat-select formControlName="status" data-test="f-status">
              <mat-option value="">All</mat-option>
              <mat-option value="waiting">Waiting</mat-option>
              <mat-option value="in_treatment">In treatment</mat-option>
              <mat-option value="discharged">Discharged</mat-option>
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Department</mat-label>
            <mat-select formControlName="department" data-test="f-dept">
              <mat-option value="">All</mat-option>
              @for (d of departments(); track d.department_code) {
                <mat-option [value]="d.department_code">{{ d.department_name }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Simulated triage category</mat-label>
            <mat-select formControlName="triage_category">
              <mat-option value="">All</mat-option>
              <mat-option value="critical">Critical</mat-option>
              <mat-option value="urgent">Urgent</mat-option>
              <mat-option value="semi_urgent">Semi-urgent</mat-option>
              <mat-option value="non_urgent">Non-urgent</mat-option>
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Investigation status</mat-label>
            <mat-select formControlName="investigation_status">
              <mat-option value="">All</mat-option>
              <mat-option value="none">None</mat-option>
              <mat-option value="pending">Pending</mat-option>
              <mat-option value="completed">Completed</mat-option>
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Arrived within</mat-label>
            <mat-select formControlName="arrived_within_minutes">
              <mat-option [value]="null">Any time</mat-option>
              <mat-option [value]="60">Last 1 hour</mat-option>
              <mat-option [value]="120">Last 2 hours</mat-option>
              <mat-option [value]="240">Last 4 hours</mat-option>
              <mat-option [value]="480">Last 8 hours</mat-option>
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline" subscriptSizing="dynamic" class="num">
            <mat-label>Min wait (min)</mat-label>
            <input matInput type="number" min="0" formControlName="min_wait_minutes" />
          </mat-form-field>
          <mat-form-field appearance="outline" subscriptSizing="dynamic" class="num">
            <mat-label>Max wait (min)</mat-label>
            <input matInput type="number" min="0" formControlName="max_wait_minutes" />
          </mat-form-field>
          <button mat-flat-button type="submit" data-test="search"><mat-icon>filter_alt</mat-icon> Apply filters</button>
          <button mat-button type="button" (click)="clear()">Clear</button>
        </form>

        <p class="count" data-test="count">{{ total() }} visits match</p>
        <div class="table-wrap">
          <table mat-table [dataSource]="rows()" aria-label="Patient visits">
            <ng-container matColumnDef="visit"><th mat-header-cell *matHeaderCellDef>Visit</th><td mat-cell *matCellDef="let r">{{ r.visit_ref }}</td></ng-container>
            <ng-container matColumnDef="patient"><th mat-header-cell *matHeaderCellDef>Patient ref</th><td mat-cell *matCellDef="let r">{{ r.patient_ref }}</td></ng-container>
            <ng-container matColumnDef="arrival"><th mat-header-cell *matHeaderCellDef>Arrival</th><td mat-cell *matCellDef="let r">{{ r.arrival_at | date: 'MMM d, HH:mm' }}</td></ng-container>
            <ng-container matColumnDef="dept"><th mat-header-cell *matHeaderCellDef>Department</th><td mat-cell *matCellDef="let r">{{ r.department_code }}</td></ng-container>
            <ng-container matColumnDef="triage"><th mat-header-cell *matHeaderCellDef>Simulated triage</th><td mat-cell *matCellDef="let r"><span class="pill" [attr.data-triage]="r.triage_category">{{ label(r.triage_category) }}</span></td></ng-container>
            <ng-container matColumnDef="status"><th mat-header-cell *matHeaderCellDef>Status</th><td mat-cell *matCellDef="let r">{{ label(r.status) }}</td></ng-container>
            <ng-container matColumnDef="wait"><th mat-header-cell *matHeaderCellDef>Waiting</th><td mat-cell *matCellDef="let r">{{ wait(r.waiting_minutes) }}</td></ng-container>
            <ng-container matColumnDef="staff"><th mat-header-cell *matHeaderCellDef>Staff ref</th><td mat-cell *matCellDef="let r">{{ r.assigned_staff_ref ?? '—' }}</td></ng-container>
            <ng-container matColumnDef="bed"><th mat-header-cell *matHeaderCellDef>Bed</th><td mat-cell *matCellDef="let r">{{ r.bed_ref ?? '—' }}</td></ng-container>
            <ng-container matColumnDef="inv"><th mat-header-cell *matHeaderCellDef>Investigation</th><td mat-cell *matCellDef="let r">{{ label(r.investigation_status) }}</td></ng-container>
            <tr mat-header-row *matHeaderRowDef="columns"></tr>
            <tr mat-row *matRowDef="let r; columns: columns"></tr>
            <tr class="mat-row" *matNoDataRow><td class="mat-cell" [attr.colspan]="columns.length">No visits match the filters.</td></tr>
          </table>
        </div>
        <mat-paginator [length]="total()" [pageIndex]="page() - 1" [pageSize]="pageSize()" [pageSizeOptions]="[25, 50, 100]"
          (page)="onPage($event)" aria-label="Visit pages" />
      </mat-tab>

      <mat-tab label="Pending investigations">
        @if (pending(); as p) {
          <section class="cards">
            <mat-card appearance="outlined"><mat-card-content><div class="label">Pending requests</div><div class="big">{{ p.pending_count }}</div></mat-card-content></mat-card>
            <mat-card appearance="outlined"><mat-card-content><div class="label">Average age</div><div class="big">{{ p.avg_age_minutes | number: '1.0-0' }} min</div></mat-card-content></mat-card>
            <mat-card appearance="outlined"><mat-card-content><div class="label">Max age</div><div class="big">{{ p.max_age_minutes | number: '1.0-0' }} min</div></mat-card-content></mat-card>
            <mat-card appearance="outlined"><mat-card-content><div class="label">Average delay beyond expected</div><div class="big">{{ p.avg_delay_minutes | number: '1.0-0' }} min</div></mat-card-content></mat-card>
          </section>
          <div class="table-wrap">
            <table mat-table [dataSource]="p.items" aria-label="Pending investigations">
              <ng-container matColumnDef="visit"><th mat-header-cell *matHeaderCellDef>Visit</th><td mat-cell *matCellDef="let r">{{ r.visit_ref }}</td></ng-container>
              <ng-container matColumnDef="dept"><th mat-header-cell *matHeaderCellDef>Department</th><td mat-cell *matCellDef="let r">{{ r.department_code }}</td></ng-container>
              <ng-container matColumnDef="facility"><th mat-header-cell *matHeaderCellDef>Facility</th><td mat-cell *matCellDef="let r">{{ r.facility_code }}</td></ng-container>
              <ng-container matColumnDef="requested"><th mat-header-cell *matHeaderCellDef>Requested</th><td mat-cell *matCellDef="let r">{{ r.requested_at | date: 'MMM d, HH:mm' }}</td></ng-container>
              <ng-container matColumnDef="age"><th mat-header-cell *matHeaderCellDef>Age</th><td mat-cell *matCellDef="let r">{{ wait(r.age_minutes) }}</td></ng-container>
              <ng-container matColumnDef="expected"><th mat-header-cell *matHeaderCellDef>Expected</th><td mat-cell *matCellDef="let r">{{ r.expected_minutes }} min</td></ng-container>
              <ng-container matColumnDef="delay"><th mat-header-cell *matHeaderCellDef>Delay</th><td mat-cell *matCellDef="let r">{{ wait(r.delay_minutes) }}</td></ng-container>
              <tr mat-header-row *matHeaderRowDef="pendingCols"></tr>
              <tr mat-row *matRowDef="let r; columns: pendingCols"></tr>
              <tr class="mat-row" *matNoDataRow><td class="mat-cell" [attr.colspan]="pendingCols.length">No pending investigations.</td></tr>
            </table>
          </div>
        }
      </mat-tab>
    </mat-tab-group>
  `,
  styles: `
    h1 { margin: 0 0 4px; font-weight: 500; }
    .meta { margin: 0 0 16px; opacity: 0.8; }
    .error { border-color: var(--ed-down); color: var(--ed-down); margin-bottom: 12px; }
    .filters { display: flex; gap: 12px; flex-wrap: wrap; padding: 16px 0 4px; align-items: center; }
    .filters mat-form-field { width: 220px; }
    .filters .num { width: 160px; }
    td.mat-mdc-cell { white-space: nowrap; }
    .count { margin: 8px 0; opacity: 0.8; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; }
    .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin: 16px 0; }
    .label { font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; opacity: 0.75; }
    .big { font-size: 28px; font-weight: 500; }
    .pill { padding: 2px 8px; border-radius: 10px; font-size: 12px; background: var(--mat-sys-surface-container-high); white-space: nowrap; }
    .pill[data-triage='critical'] { background: #fee2e2; color: #7f1d1d; }
    .pill[data-triage='urgent'] { background: #ffedd5; color: #7c2d12; }
    .pill[data-triage='semi_urgent'] { background: #fef9c3; color: #713f12; }
    .pill[data-triage='non_urgent'] { background: #dcfce7; color: #14532d; }
  `,
})
export class QueuePage {
  protected readonly scenario = inject(ScenarioService);
  private readonly api = inject(QueueService);
  private readonly resources = inject(ResourceService);
  private readonly fb = inject(FormBuilder);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly columns = ['visit', 'patient', 'arrival', 'dept', 'triage', 'status', 'wait', 'staff', 'bed', 'inv'];
  protected readonly pendingCols = ['visit', 'dept', 'facility', 'requested', 'age', 'expected', 'delay'];

  protected readonly filters = this.fb.group({
    status: [''],
    department: [''],
    triage_category: [''],
    investigation_status: [''],
    arrived_within_minutes: [null as number | null],
    min_wait_minutes: [null as number | null],
    max_wait_minutes: [null as number | null],
  });

  protected readonly departments = signal<DepartmentCapacity[]>([]);
  protected readonly rows = signal<QueueRow[]>([]);
  protected readonly total = signal(0);
  protected readonly page = signal(1);
  protected readonly pageSize = signal(25);
  protected readonly pending = signal<PendingInvestigations | null>(null);
  protected readonly error = signal<string | null>(null);

  protected readonly wait = formatWait;

  constructor() {
    this.scenario.refreshState().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({ error: () => undefined });
    effect(() => {
      const v = this.scenario.dataVersion();
      if (v === null) return;
      untracked(() => {
        this.resources
          .departments()
          .pipe(takeUntilDestroyed(this.destroyRef))
          .subscribe({ next: (d) => this.departments.set(d), error: () => undefined });
        this.load();
        this.loadPending();
      });
    });
  }

  protected label(v: string): string {
    return v.replace('_', ' ').replace(/^./, (c) => c.toUpperCase());
  }

  protected search(): void {
    this.page.set(1);
    this.load();
  }

  protected clear(): void {
    this.filters.reset({
      status: '',
      department: '',
      triage_category: '',
      investigation_status: '',
      arrived_within_minutes: null,
      min_wait_minutes: null,
      max_wait_minutes: null,
    });
    this.search();
  }

  protected onPage(e: PageEvent): void {
    this.page.set(e.pageIndex + 1);
    this.pageSize.set(e.pageSize);
    this.load();
  }

  protected load(): void {
    const f = this.filters.getRawValue();
    const q: QueueQuery = {
      status: f.status as QueueQuery['status'],
      department: f.department ?? undefined,
      triage_category: f.triage_category as QueueQuery['triage_category'],
      investigation_status: f.investigation_status as QueueQuery['investigation_status'],
      arrived_within_minutes: f.arrived_within_minutes,
      min_wait_minutes: f.min_wait_minutes,
      max_wait_minutes: f.max_wait_minutes,
      page: this.page(),
      page_size: this.pageSize(),
    };
    this.api
      .list(q)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (p) => {
          this.rows.set(p.items);
          this.total.set(p.total);
          this.error.set(null);
        },
        error: (e) => this.error.set(apiErrorMessage(e)),
      });
  }

  private loadPending(): void {
    this.api
      .pendingInvestigations(undefined, 100)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({ next: (p) => this.pending.set(p), error: () => undefined });
  }
}
