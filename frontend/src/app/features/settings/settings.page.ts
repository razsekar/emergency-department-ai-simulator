import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { describeApiError } from '../../core/api-error';
import { ProvidersService, ProviderStatus } from '../playground/providers.service';

/** Read-only provider configuration status. Secrets are never returned by the API, so none are shown. */
@Component({
  selector: 'app-settings-page',
  imports: [MatButtonModule, MatCardModule, MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1>Settings</h1>
    <p class="muted">
      Provider keys are configured in the backend environment (<code>.env</code>) and are never sent to the browser.
    </p>

    <div class="actions">
      <button mat-stroked-button type="button" (click)="refresh()" [disabled]="loading()">
        <mat-icon>refresh</mat-icon> Re-check (includes Ollama reachability)
      </button>
    </div>

    @if (error()) {
      <p class="error" role="alert">{{ error() }}</p>
    }

    <div class="grid">
      @for (s of statuses(); track s.provider) {
        <mat-card appearance="outlined">
          <mat-card-header>
            <mat-card-title>{{ s.label }}</mat-card-title>
            <mat-card-subtitle>{{ s.cloud ? 'Cloud provider' : 'Local provider' }}</mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            <p>
              <span class="badge" [attr.data-ok]="s.configured">{{ s.configured ? 'Configured' : 'Not configured' }}</span>
              @if (s.reachable !== null) {
                <span class="badge" [attr.data-ok]="s.reachable">{{ s.reachable ? 'Reachable' : 'Unreachable' }}</span>
              }
            </p>
            <p class="small">{{ s.detail }}</p>
            @if (s.cloud) {
              <p class="small disclosure">
                <mat-icon aria-hidden="true">cloud_upload</mat-icon>
                {{ s.data_disclosure ?? 'Prompts and document context are sent to this provider.' }}
              </p>
            }
          </mat-card-content>
        </mat-card>
      }
    </div>
  `,
  styles: `
    :host { display: block; max-width: 1000px; }
    h1 { margin: 0 0 4px; }
    .muted { color: #5f6b7a; }
    .actions { margin: 12px 0; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
    .badge { padding: 2px 10px; border-radius: 12px; font-size: 12px; background: #e8f5e9; color: #1b5e20; margin-right: 6px; }
    .badge[data-ok='false'] { background: #fdecea; color: #8a1c14; }
    .small { font-size: 13px; }
    .disclosure { display: flex; gap: 6px; align-items: center; color: #5b3b00; }
    .error { color: #b3261e; }
  `,
})
export class SettingsPage {
  private readonly providers = inject(ProvidersService);
  protected readonly statuses = signal<ProviderStatus[]>([]);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  constructor() {
    this.refresh();
  }

  protected refresh(): void {
    this.loading.set(true);
    this.error.set(null);
    this.providers.status(true).subscribe({
      next: (s) => {
        this.statuses.set(s);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(describeApiError(err));
        this.loading.set(false);
      },
    });
  }
}
