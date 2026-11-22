import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { describeApiError } from '../../core/api-error';
import { Permissions } from '../../core/auth/auth.models';
import { AuthService } from '../../core/auth/auth.service';
import { KnowledgeDocument, KnowledgeService, SearchResponse, validatePdf } from './knowledge.service';

@Component({
  selector: 'app-knowledge-page',
  imports: [DatePipe, FormsModule, MatButtonModule, MatCardModule, MatFormFieldModule, MatIconModule, MatInputModule, MatProgressBarModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1>Knowledge Base</h1>
    <p class="muted">
      Fictional demonstration policies only. Retrieved text is treated as untrusted data and never overrides hospital protocols or clinical judgment.
    </p>

    @if (error()) {
      <p class="error" role="alert">{{ error() }}</p>
    }
    @if (info()) {
      <p class="info" role="status">{{ info() }}</p>
    }

    <mat-card appearance="outlined">
      <mat-card-header>
        <mat-card-title>Documents</mat-card-title>
        <mat-card-subtitle>{{ total() }} indexed</mat-card-subtitle>
      </mat-card-header>
      <mat-card-content>
        @if (canUpload()) {
          <div class="actions">
            <input #file type="file" accept="application/pdf,.pdf" hidden (change)="onFile($event)" />
            <button mat-flat-button type="button" (click)="file.click()" [disabled]="busy()">
              <mat-icon>upload_file</mat-icon> Upload PDF
            </button>
            <button mat-stroked-button type="button" (click)="loadSamples()" [disabled]="busy()">
              <mat-icon>library_add</mat-icon> Load sample policies
            </button>
          </div>
        } @else {
          <p class="muted small">Your role can read documents but not upload or delete them.</p>
        }
        @if (busy()) {
          <mat-progress-bar mode="indeterminate" />
        }

        <table class="docs">
          <thead>
            <tr><th>Name</th><th>Pages</th><th>Chunks</th><th>Status</th><th>Added</th><th></th></tr>
          </thead>
          <tbody>
            @for (d of documents(); track d.id) {
              <tr>
                <td>
                  {{ d.name }}
                  @if (d.is_sample) { <span class="tag">sample</span> }
                </td>
                <td>{{ d.page_count }}</td>
                <td>{{ d.chunk_count }}</td>
                <td>
                  <span class="status" [attr.data-status]="d.status" [title]="d.error_message ?? ''">{{ d.status }}</span>
                </td>
                <td>{{ d.created_at | date: 'short' }}</td>
                <td>
                  @if (canUpload()) {
                    <button mat-icon-button type="button" (click)="remove(d)" [attr.aria-label]="'Delete ' + d.name">
                      <mat-icon>delete</mat-icon>
                    </button>
                  }
                </td>
              </tr>
            } @empty {
              <tr><td colspan="6" class="muted">No documents yet. Load the sample policies or upload a PDF.</td></tr>
            }
          </tbody>
        </table>
      </mat-card-content>
    </mat-card>

    <mat-card appearance="outlined" class="search">
      <mat-card-header>
        <mat-card-title>Similarity search</mat-card-title>
        <mat-card-subtitle>Vector search over document chunks</mat-card-subtitle>
      </mat-card-header>
      <mat-card-content>
        <form class="row" (submit)="$event.preventDefault(); search()">
          <mat-form-field appearance="outline" class="grow">
            <mat-label>Query</mat-label>
            <input matInput name="q" [ngModel]="query()" (ngModelChange)="query.set($event)" maxlength="2000" />
          </mat-form-field>
          <button mat-flat-button type="submit" [disabled]="!query().trim() || searching()">Search</button>
        </form>

        @if (results(); as r) {
          <p class="muted small">{{ r.results.length }} results · embedding model {{ r.embedding_model }}</p>
          @for (c of r.results; track c.chunk_id) {
            <article class="hit" [attr.data-flagged]="c.injection_flagged">
              <header>
                <strong>{{ c.document_name }}</strong>
                <span>page {{ c.page_number }}</span>
                <span class="score" title="Cosine similarity">score {{ c.score.toFixed(3) }}</span>
              </header>
              @if (c.injection_flagged) {
                <p class="warn">
                  <mat-icon aria-hidden="true">warning</mat-icon>
                  Flagged as possible prompt injection ({{ c.injection_signals.join(', ') || 'instruction-like text' }}).
                  This excerpt is withheld from LLM context.
                </p>
              }
              <blockquote>{{ c.excerpt }}</blockquote>
            </article>
          } @empty {
            <p class="muted">No matching chunks.</p>
          }
        }
      </mat-card-content>
    </mat-card>
  `,
  styles: `
    :host { display: block; max-width: 1000px; }
    h1 { margin: 0 0 4px; }
    .muted { color: #5f6b7a; }
    .small { font-size: 12px; }
    .error { color: #b3261e; }
    .info { color: #1b5e20; }
    mat-card { margin-bottom: 16px; }
    .actions, .row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin: 12px 0; }
    .grow { flex: 1 1 320px; }
    .docs { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 14px; }
    .docs th, .docs td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #e3e8ef; }
    .tag { font-size: 11px; background: #e8eef7; color: #1f3a5f; border-radius: 8px; padding: 1px 6px; margin-left: 6px; }
    .status { padding: 1px 8px; border-radius: 10px; background: #e8f5e9; color: #1b5e20; font-size: 12px; }
    .status[data-status='failed'] { background: #fdecea; color: #8a1c14; }
    .hit { border: 1px solid #e3e8ef; border-radius: 8px; padding: 10px 12px; margin: 10px 0; }
    .hit[data-flagged='true'] { border-color: #f0c36d; background: #fffaf0; }
    .hit header { display: flex; gap: 12px; flex-wrap: wrap; font-size: 13px; }
    .score { margin-left: auto; color: #5f6b7a; }
    blockquote { margin: 8px 0 0; padding-left: 10px; border-left: 3px solid #c5d3e8; white-space: pre-wrap; font-size: 13px; }
    .warn { display: flex; gap: 6px; align-items: center; color: #7a4b00; font-size: 13px; margin: 6px 0 0; }
  `,
})
export class KnowledgePage {
  private readonly kb = inject(KnowledgeService);
  private readonly auth = inject(AuthService);

  protected readonly documents = signal<KnowledgeDocument[]>([]);
  protected readonly total = signal(0);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly info = signal<string | null>(null);

  protected readonly query = signal('');
  protected readonly searching = signal(false);
  protected readonly results = signal<SearchResponse | null>(null);

  protected readonly canUpload = computed(() => this.auth.hasPermission(Permissions.KnowledgeUpload));

  constructor() {
    this.reload();
  }

  protected reload(): void {
    this.kb.list().subscribe({
      next: (page) => {
        this.documents.set(page.items);
        this.total.set(page.total);
      },
      error: (err: unknown) => this.error.set(describeApiError(err)),
    });
  }

  protected onFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = ''; // allow re-selecting the same file
    if (!file) return;
    const problem = validatePdf(file);
    if (problem) {
      this.error.set(problem);
      return;
    }
    this.begin();
    this.kb.upload(file).subscribe({
      next: (doc) => this.done(`Uploaded “${doc.name}” (${doc.status}).`),
      error: (err: unknown) => this.fail(err),
    });
  }

  protected loadSamples(): void {
    this.begin();
    this.kb.loadSamples().subscribe({
      next: (r) => this.done(`Loaded ${r.loaded.length} sample document(s); ${r.skipped.length} already present.`),
      error: (err: unknown) => this.fail(err),
    });
  }

  protected remove(doc: KnowledgeDocument): void {
    if (!window.confirm(`Delete “${doc.name}” and its indexed chunks?`)) return;
    this.begin();
    this.kb.delete(doc.id).subscribe({
      next: () => this.done(`Deleted “${doc.name}”.`),
      error: (err: unknown) => this.fail(err),
    });
  }

  protected search(): void {
    const q = this.query().trim();
    if (!q) return;
    this.searching.set(true);
    this.error.set(null);
    this.kb.search(q).subscribe({
      next: (r) => {
        this.results.set(r);
        this.searching.set(false);
      },
      error: (err: unknown) => {
        this.error.set(describeApiError(err));
        this.searching.set(false);
      },
    });
  }

  private begin(): void {
    this.busy.set(true);
    this.error.set(null);
    this.info.set(null);
  }

  private done(message: string): void {
    this.busy.set(false);
    this.info.set(message);
    this.reload();
  }

  private fail(err: unknown): void {
    this.busy.set(false);
    this.error.set(describeApiError(err));
  }
}
