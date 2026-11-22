import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { forkJoin } from 'rxjs';
import { describeApiError } from '../../core/api-error';
import { AuthService } from '../../core/auth/auth.service';
import { Permissions } from '../../core/auth/auth.models';
import { ChatStreamService } from './chat-stream.service';
import { CloudDisclosure } from './cloud-disclosure.component';
import { ModelPicker } from './model-picker.component';
import {
  ChatResponse,
  ModelInfo,
  ProviderName,
  ProvidersService,
  ProviderStatus,
  formatCost,
  formatTokens,
} from './providers.service';

@Component({
  selector: 'app-playground-page',
  imports: [
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressBarModule,
    ModelPicker,
    CloudDisclosure,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1>Model Playground</h1>
    <p class="muted">Choose a provider and model, then send a prompt. Keys stay on the server and are never shown here.</p>

    @if (loadError()) {
      <p class="error" role="alert">{{ loadError() }}</p>
    }

    <mat-card appearance="outlined">
      <mat-card-content>
        <app-model-picker
          [statuses]="statuses()"
          [models]="models()"
          [(provider)]="provider"
          [(modelId)]="modelId"
          [(temperature)]="temperature"
          [(streaming)]="streaming"
        />

        @if (selectedStatus(); as st) {
          <div class="badges">
            <span class="badge" [attr.data-ok]="st.configured">{{ st.configured ? 'Configured' : 'Not configured' }}</span>
            @if (st.reachable !== null) {
              <span class="badge" [attr.data-ok]="st.reachable">{{ st.reachable ? 'Reachable' : 'Unreachable' }}</span>
            }
            <span class="badge" [attr.data-ok]="selectedModel()?.supports_tools ?? 'unknown'">
              Tool calling: {{ toolSupport() }}
            </span>
            <span class="badge neutral">{{ st.cloud ? 'Cloud' : 'Local' }}</span>
          </div>
          <p class="muted small">{{ st.detail }}</p>
          <app-cloud-disclosure [cloud]="st.cloud" [text]="st.data_disclosure" />
        }

        <mat-form-field appearance="outline" class="full">
          <mat-label>System prompt (optional)</mat-label>
          <textarea matInput rows="2" [ngModel]="system()" (ngModelChange)="system.set($event)"></textarea>
        </mat-form-field>
        <mat-form-field appearance="outline" class="full">
          <mat-label>Prompt</mat-label>
          <textarea matInput rows="5" [ngModel]="prompt()" (ngModelChange)="prompt.set($event)"></textarea>
        </mat-form-field>
        <div class="actions">
          <button mat-flat-button type="button" (click)="send()" [disabled]="!canSend()">
            {{ busy() ? 'Generating…' : 'Send' }}
          </button>
          @if (busy()) {
            <button mat-button type="button" (click)="cancel()">Stop</button>
          }
          @if (!canChat()) {
            <span class="muted small">Your role cannot send chat requests.</span>
          }
        </div>
        @if (busy()) {
          <mat-progress-bar mode="indeterminate" />
        }
      </mat-card-content>
    </mat-card>

    @if (error()) {
      <p class="error" role="alert">{{ error() }}</p>
    }

    @if (output() || result()) {
      <mat-card appearance="outlined" class="result">
        <mat-card-header>
          <mat-card-title>Response</mat-card-title>
          @if (result(); as r) {
            <mat-card-subtitle>{{ r.provider }} · {{ r.model }}</mat-card-subtitle>
          }
        </mat-card-header>
        <mat-card-content>
          <pre class="output">{{ output() }}</pre>
          @if (result(); as r) {
            <dl class="metrics">
              <dt>Latency</dt><dd>{{ r.latency_ms }} ms</dd>
              <dt>Tokens</dt><dd>{{ tokens(r) }}</dd>
              <dt>Estimated cost</dt><dd>{{ cost(r) }}</dd>
              <dt>Finish reason</dt><dd>{{ r.finish_reason ?? 'n/a' }}</dd>
              @if (!r.temperature_applied) {
                <dt>Temperature</dt><dd>Not supported by this model (ignored)</dd>
              }
            </dl>
            <p class="muted small">Cost is an estimate from a bundled price list and may be out of date.</p>
          }
        </mat-card-content>
      </mat-card>
    }
  `,
  styles: `
    :host { display: block; max-width: 960px; }
    h1 { margin: 0 0 4px; }
    .muted { color: #5f6b7a; margin: 0 0 12px; }
    .small { font-size: 12px; }
    .full { width: 100%; }
    .badges { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 4px; }
    .badge { padding: 2px 10px; border-radius: 12px; font-size: 12px; background: #e8f5e9; color: #1b5e20; }
    .badge[data-ok='false'] { background: #fdecea; color: #8a1c14; }
    .badge[data-ok='unknown'] { background: #eceff3; color: #3b4654; }
    .badge.neutral { background: #e8eef7; color: #1f3a5f; }
    .actions { display: flex; gap: 12px; align-items: center; }
    .result { margin-top: 16px; }
    .output { white-space: pre-wrap; font-family: inherit; margin: 0 0 12px; }
    .metrics { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; margin: 0; font-size: 13px; }
    .metrics dt { color: #5f6b7a; }
    .metrics dd { margin: 0; }
    .error { color: #b3261e; }
  `,
})
export class PlaygroundPage {
  private readonly providers = inject(ProvidersService);
  private readonly streamer = inject(ChatStreamService);
  private readonly auth = inject(AuthService);

  protected readonly statuses = signal<ProviderStatus[]>([]);
  protected readonly models = signal<ModelInfo[]>([]);
  protected readonly provider = signal<ProviderName | null>(null);
  protected readonly modelId = signal<string | null>(null);
  protected readonly temperature = signal(0.2);
  protected readonly streaming = signal(true);

  protected readonly system = signal('');
  protected readonly prompt = signal('');
  protected readonly busy = signal(false);
  protected readonly output = signal('');
  protected readonly result = signal<ChatResponse | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly loadError = signal<string | null>(null);

  private abort: AbortController | null = null;

  protected readonly selectedStatus = computed(() => this.statuses().find((s) => s.provider === this.provider()) ?? null);
  protected readonly selectedModel = computed(
    () => this.models().find((m) => m.provider === this.provider() && m.model_id === this.modelId()) ?? null,
  );
  protected readonly canChat = computed(() => this.auth.hasPermission(Permissions.AiChat));
  protected readonly canSend = computed(
    () => this.canChat() && !this.busy() && !!this.modelId() && !!this.provider() && this.prompt().trim().length > 0,
  );
  protected readonly toolSupport = computed(() => {
    const s = this.selectedModel()?.supports_tools;
    return s === true ? 'supported' : s === false ? 'not supported' : 'unknown';
  });

  protected tokens = (r: ChatResponse) => formatTokens(r.usage);
  protected cost = (r: ChatResponse) => formatCost(r.estimated_cost_usd);

  constructor() {
    forkJoin({ statuses: this.providers.status(true), models: this.providers.models() }).subscribe({
      next: ({ statuses, models }) => {
        this.statuses.set(statuses);
        this.models.set(models);
      },
      error: (err: unknown) => this.loadError.set(describeApiError(err)),
    });
  }

  protected cancel(): void {
    this.abort?.abort();
  }

  protected async send(): Promise<void> {
    const provider = this.provider();
    const model = this.modelId();
    if (!provider || !model || this.busy()) return;

    const messages = [
      ...(this.system().trim() ? [{ role: 'system' as const, content: this.system().trim() }] : []),
      { role: 'user' as const, content: this.prompt().trim() },
    ];
    const request = { provider, model, messages, temperature: this.temperature() };

    this.busy.set(true);
    this.error.set(null);
    this.output.set('');
    this.result.set(null);
    this.abort = new AbortController();

    try {
      if (this.streaming()) {
        await this.streamer.stream(
          request,
          (e) => {
            if (e.type === 'delta' && e.content) this.output.update((o) => o + e.content);
            else if (e.type === 'done' && e.response) this.result.set(e.response);
            else if (e.type === 'error') this.error.set(e.message ?? 'The provider reported an error.');
          },
          this.abort.signal,
        );
      } else {
        const r = await new Promise<ChatResponse>((resolve, reject) =>
          this.providers.chat(request).subscribe({ next: resolve, error: reject }),
        );
        this.output.set(r.content ?? '');
        this.result.set(r);
      }
    } catch (err) {
      if (!(err instanceof DOMException && err.name === 'AbortError')) this.error.set(describeApiError(err));
    } finally {
      this.busy.set(false);
      this.abort = null;
    }
  }
}
