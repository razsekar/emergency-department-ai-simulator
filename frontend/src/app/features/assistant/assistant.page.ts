import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { forkJoin } from 'rxjs';
import { describeApiError } from '../../core/api-error';
import { Permissions } from '../../core/auth/auth.models';
import { AuthService } from '../../core/auth/auth.service';
import { CloudDisclosure } from '../playground/cloud-disclosure.component';
import { ModelPicker } from '../playground/model-picker.component';
import {
  ChatResponse,
  ModelInfo,
  ProviderName,
  ProvidersService,
  ProviderStatus,
  formatCost,
  formatTokens,
} from '../playground/providers.service';
import { AssistantBackend, ProviderChatBackend } from './assistant-backend';

interface Turn {
  role: 'user' | 'assistant';
  content: string;
  meta?: ChatResponse;
  error?: boolean;
}

@Component({
  selector: 'app-assistant-page',
  imports: [FormsModule, MatButtonModule, MatCardModule, MatFormFieldModule, MatIconModule, MatInputModule, ModelPicker, CloudDisclosure],
  providers: [{ provide: AssistantBackend, useExisting: ProviderChatBackend }],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1>AI Assistant</h1>
    @if (!backend.grounded) {
      <div class="notice" role="note">
        <mat-icon aria-hidden="true">info</mat-icon>
        <span>
          This assistant is not yet connected to retrieved hospital policies, so answers carry <strong>no citations</strong>
          and are general explanations only. Policy-grounded answers arrive with the RAG chat endpoint.
        </span>
      </div>
    }

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
        <app-cloud-disclosure [cloud]="selectedStatus()?.cloud ?? false" [text]="selectedStatus()?.data_disclosure ?? null" />
      </mat-card-content>
    </mat-card>

    <section class="transcript" aria-live="polite">
      @for (t of turns(); track $index) {
        <div class="turn" [attr.data-role]="t.role" [attr.data-error]="t.error ?? false">
          <div class="who">{{ t.role === 'user' ? 'You' : 'Assistant' }}</div>
          <div class="text">{{ t.content }}</div>
          @if (t.meta; as m) {
            <div class="meta">
              {{ m.provider }} · {{ m.model }} · {{ m.latency_ms }} ms · {{ tokens(m) }} · est. {{ cost(m) }}
            </div>
          }
        </div>
      } @empty {
        <p class="muted">Ask a question about operations. Ground-truth numbers come from the dashboard, not from this chat.</p>
      }
    </section>

    <form class="composer" (submit)="$event.preventDefault(); send()">
      <mat-form-field appearance="outline" class="grow">
        <mat-label>Message</mat-label>
        <textarea
          matInput
          rows="2"
          [ngModel]="draft()"
          (ngModelChange)="draft.set($event)"
          name="draft"
          (keydown.enter)="onEnter($event)"
        ></textarea>
      </mat-form-field>
      <button mat-flat-button type="submit" [disabled]="!canSend()">{{ busy() ? 'Generating…' : 'Send' }}</button>
      @if (busy()) {
        <button mat-button type="button" (click)="cancel()">Stop</button>
      }
    </form>
    @if (!canChat()) {
      <p class="muted">Your role cannot send chat requests.</p>
    }
  `,
  styles: `
    :host { display: block; max-width: 960px; }
    h1 { margin: 0 0 8px; }
    .notice { display: flex; gap: 8px; align-items: center; padding: 8px 12px; margin-bottom: 12px; border-radius: 8px;
      background: #e8eef7; color: #1f3a5f; font-size: 13px; }
    .transcript { margin: 16px 0; display: flex; flex-direction: column; gap: 12px; }
    .turn { padding: 10px 14px; border-radius: 10px; background: #f3f6fa; }
    .turn[data-role='user'] { background: #e3f0ff; }
    .turn[data-error='true'] { background: #fdecea; color: #8a1c14; }
    .who { font-size: 12px; font-weight: 600; margin-bottom: 4px; opacity: 0.7; }
    .text { white-space: pre-wrap; }
    .meta { font-size: 12px; opacity: 0.65; margin-top: 6px; }
    .composer { display: flex; gap: 12px; align-items: flex-start; }
    .grow { flex: 1; }
    .muted { color: #5f6b7a; }
    .error { color: #b3261e; }
  `,
})
export class AssistantPage {
  protected readonly backend = inject(AssistantBackend);
  private readonly providers = inject(ProvidersService);
  private readonly auth = inject(AuthService);

  protected readonly statuses = signal<ProviderStatus[]>([]);
  protected readonly models = signal<ModelInfo[]>([]);
  protected readonly provider = signal<ProviderName | null>(null);
  protected readonly modelId = signal<string | null>(null);
  protected readonly temperature = signal(0.2);
  protected readonly streaming = signal(true);

  protected readonly turns = signal<Turn[]>([]);
  protected readonly draft = signal('');
  protected readonly busy = signal(false);
  protected readonly loadError = signal<string | null>(null);
  private abort: AbortController | null = null;

  protected readonly selectedStatus = computed(() => this.statuses().find((s) => s.provider === this.provider()) ?? null);
  protected readonly selectedModel = computed(
    () => this.models().find((m) => m.provider === this.provider() && m.model_id === this.modelId()) ?? null,
  );
  protected readonly canChat = computed(() => this.auth.hasPermission(Permissions.AiChat));
  protected readonly canSend = computed(() => this.canChat() && !this.busy() && !!this.selectedModel() && this.draft().trim().length > 0);

  protected tokens = (r: ChatResponse) => formatTokens(r.usage);
  protected cost = (r: ChatResponse) => formatCost(r.estimated_cost_usd);

  constructor() {
    forkJoin({ statuses: this.providers.status(), models: this.providers.models() }).subscribe({
      next: ({ statuses, models }) => {
        this.statuses.set(statuses);
        this.models.set(models);
      },
      error: (err: unknown) => this.loadError.set(describeApiError(err)),
    });
  }

  protected onEnter(event: Event): void {
    const e = event as KeyboardEvent;
    if (!e.shiftKey) {
      e.preventDefault();
      void this.send();
    }
  }

  protected cancel(): void {
    this.abort?.abort();
  }

  protected async send(): Promise<void> {
    const model = this.selectedModel();
    if (!model || !this.canSend()) return;

    const history = [...this.turns().filter((t) => !t.error).map((t) => ({ role: t.role, content: t.content })), { role: 'user' as const, content: this.draft().trim() }];
    this.turns.update((t) => [...t, { role: 'user', content: this.draft().trim() }, { role: 'assistant', content: '' }]);
    this.draft.set('');
    this.busy.set(true);
    this.abort = new AbortController();

    const patchLast = (patch: Partial<Turn>) =>
      this.turns.update((ts) => ts.map((t, i) => (i === ts.length - 1 ? { ...t, ...patch } : t)));

    try {
      await this.backend.send(
        { model, temperature: this.temperature(), history },
        (e) => {
          if (e.type === 'delta' && e.content) {
            this.turns.update((ts) => ts.map((t, i) => (i === ts.length - 1 ? { ...t, content: t.content + e.content } : t)));
          } else if (e.type === 'done' && e.response) {
            patchLast({ meta: e.response });
          } else if (e.type === 'error') {
            patchLast({ content: e.message ?? 'The provider reported an error.', error: true });
          }
        },
        this.abort.signal,
      );
    } catch (err) {
      if (!(err instanceof DOMException && err.name === 'AbortError')) {
        patchLast({ content: describeApiError(err), error: true });
      }
    } finally {
      this.busy.set(false);
      this.abort = null;
    }
  }
}
