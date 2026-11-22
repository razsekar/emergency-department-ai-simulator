import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';
import { ScenarioService } from './simulator.service';

/** Persistent toolbar indicator: current scenario name and data version (read from the database). */
@Component({
  selector: 'app-scenario-status',
  imports: [MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @let s = scenario.state();
    <span class="pill" [attr.data-scenario]="s?.scenario_key ?? 'none'" aria-live="polite">
      <mat-icon aria-hidden="true">tune</mat-icon>
      <span class="name">{{ s ? (s.scenario_name ?? 'No scenario loaded') : 'Loading scenario…' }}</span>
      @if (s) {
        <span class="version" title="Data version increments on every scenario change">
          data v{{ s.data_version }}
        </span>
      }
    </span>
  `,
  styles: `
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 2px 12px 2px 8px;
      border-radius: 16px;
      font-size: 13px;
      font-weight: 500;
      white-space: nowrap;
      background: var(--mat-sys-surface-container-high);
      border: 2px solid var(--ed-unknown);
      mat-icon { font-size: 18px; width: 18px; height: 18px; }
    }
    .version { opacity: 0.8; font-variant-numeric: tabular-nums; }
    .pill[data-scenario='normal'] { border-color: #15803d; }
    .pill[data-scenario='surge'] { border-color: #b91c1c; background: #fee2e2; color: #7f1d1d; }
    .pill[data-scenario='recovery'] { border-color: #0369a1; }
    .pill[data-scenario='custom'] { border-color: #7e22ce; }
    @media (max-width: 600px) { .version { display: none; } }
  `,
})
export class ScenarioStatusComponent {
  protected readonly scenario = inject(ScenarioService);

  constructor() {
    this.scenario.refreshState().subscribe({ error: () => undefined });
  }
}
