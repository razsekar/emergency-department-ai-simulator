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
  ModelInfo,
  ProviderName,
  ProvidersService,
  ProviderStatus,
  formatCost,
  formatTokens,
} from '../playground/providers.service';
import { RetrievedPolicyView } from '../agent/agent.models';
import { AnswerParagraph, parseAnswer } from '../agent/answer-parser';
import { PolicySources } from '../../shared/policy-sources.component';
import { AssistantBackend, AssistantEvent, RagChatBackend, TurnMeta } from './assistant-backend';

interface Turn {
  role: 'user' | 'assistant';
  content: string;
  sources?: RetrievedPolicyView[];
  meta?: TurnMeta;
  error?: boolean;
}

@Component({
  selector: 'app-assistant-page',
  imports: [FormsModule, MatButtonModule, MatCardModule, MatFormFieldModule, MatIconModule, MatInputModule, ModelPicker, CloudDisclosure, PolicySources],
  providers: [{ provide: AssistantBackend, useExisting: RagChatBackend }],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1>AI Assistant</h1>
    @if (backend.grounded) {
      <div class="notice" role="note">
        <mat-icon aria-hidden="true">menu_book</mat-icon>
        <span>
          Each answer is written from <strong>retrieved policy excerpts</strong> and a fresh live-data snapshot. Excerpts are
          listed under the answer; the backend checks every <em>[Source: …]</em> citation against what was retrieved.
          Text without a citation has no policy source: do not treat it as hospital policy.
        </span>
      </div>
    } @else {
      <div class="notice" role="note">
        <mat-icon aria-hidden="true">info</mat-icon>
        <span>Plain model chat: answers carry <strong>no citations</strong> and are general explanations only.</span>
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
          @if (t.role === 'assistant' && !t.error) {
            @for (p of paragraphs(t); track $index) {
              <p class="para" [attr.data-kind]="backend.grounded ? p.kind : 'plain'">
                @for (seg of p.segments; track $index) {
                  @if (seg.kind === 'citation') {
                    <span class="cite" [attr.data-verified]="seg.verified">{{ seg.text }} {{ seg.verified ? '✓' : '⚠ unverified' }}</span>
                  } @else {
                    {{ seg.text }}
                  }
                }
              </p>
            }
          } @else {
            <div class="text">{{ t.content }}</div>
          }
          @if (t.sources && t.sources.length) {
            <details class="srcs">
              <summary>Retrieved policy excerpts ({{ t.sources.length }}): from the knowledge base, not the model</summary>
              <app-policy-sources [sources]="t.sources" />
            </details>
          }
          @if (t.meta; as m) {
            @if (m.citation_check && backend.grounded) {
              <div class="meta" [attr.data-bad]="(m.citation_check.unverified_count ?? 0) > 0">
                Citation check: {{ m.citation_check.verified_count ?? 0 }} verified, {{ m.citation_check.unverified_count ?? 0 }} unverified
              </div>
            }
            <div class="meta">
              {{ m.provider }} · {{ m.model }} · {{ m.latency_ms ?? '?' }} ms · {{ tokens(m) }} · est. {{ cost(m) }}
            </div>
            @if (m.data_disclosure) {
              <div class="meta">{{ m.data_disclosure }}</div>
            }
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
      <button mat-button type="button" (click)="newConversation()" [disabled]="busy() || turns().length === 0">New conversation</button>
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
    .meta[data-bad='true'] { color: #8a1c14; opacity: 1; font-weight: 500; }
    .para { margin: 0 0 6px; padding-left: 10px; border-left: 4px solid #9ca3af; white-space: pre-wrap; }
    .para[data-kind='policy'] { border-left-color: #1d4ed8; }
    .para[data-kind='plain'] { border-left-color: transparent; }
    .cite { font-weight: 500; border-radius: 4px; padding: 0 4px; background: #dcfce7; color: #14532d; }
    .cite[data-verified='false'] { background: #fee2e2; color: #7f1d1d; }
    .srcs { margin-top: 8px; font-size: 13px; }
    .srcs summary { cursor: pointer; }
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

  protected tokens = (m: TurnMeta) => formatTokens(m.usage);
  protected cost = (m: TurnMeta) => formatCost(m.estimated_cost_usd);
  protected paragraphs = (t: Turn): AnswerParagraph[] => parseAnswer(t.content, t.meta?.citation_check);

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

  protected newConversation(): void {
    this.backend.reset();
    this.turns.set([]);
  }

  protected async send(): Promise<void> {
    const model = this.selectedModel();
    if (!model || !this.canSend()) return;

    const text = this.draft().trim();
    const history = [...this.turns().filter((t) => !t.error).map((t) => ({ role: t.role, content: t.content })), { role: 'user' as const, content: text }];
    this.turns.update((t) => [...t, { role: 'user', content: text }, { role: 'assistant', content: '' }]);
    this.draft.set('');
    this.busy.set(true);
    this.abort = new AbortController();

    const patchLast = (patch: Partial<Turn>) =>
      this.turns.update((ts) => ts.map((t, i) => (i === ts.length - 1 ? { ...t, ...patch } : t)));

    try {
      await this.backend.send(
        { model, temperature: this.temperature(), content: text, history, streaming: this.streaming() },
        (e: AssistantEvent) => {
          if (e.type === 'sources') {
            patchLast({ sources: e.sources });
          } else if (e.type === 'delta') {
            this.turns.update((ts) => ts.map((t, i) => (i === ts.length - 1 ? { ...t, content: t.content + e.content } : t)));
          } else if (e.type === 'done') {
            patchLast({ meta: e.meta });
          } else if (e.type === 'error') {
            patchLast({ content: e.message, error: true });
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
