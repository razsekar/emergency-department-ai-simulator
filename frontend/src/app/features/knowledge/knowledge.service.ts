import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

/** Mirrors backend/app/modules/knowledge_base/api/schemas.py and rag/api/schemas.py */
export interface KnowledgeDocument {
  id: string;
  name: string;
  original_filename: string;
  size_bytes: number;
  page_count: number;
  status: string;
  chunk_count: number;
  error_message: string | null;
  is_sample: boolean;
  created_at: string;
  updated_at: string;
}

export interface DocumentPage {
  items: KnowledgeDocument[];
  total: number;
  limit: number;
  offset: number;
}

export interface SampleLoadResult {
  loaded: string[];
  skipped: string[];
}

export interface SearchChunk {
  chunk_id: string;
  document_id: string;
  document_name: string;
  page_number: number;
  chunk_index: number;
  excerpt: string;
  score: number;
  injection_flagged: boolean;
  injection_signals: string[];
}

export interface SearchResponse {
  query: string;
  embedding_model: string;
  results: SearchChunk[];
  llm_context: string;
}

/** Client-side limit mirrors the backend default (10 MB); the server remains authoritative. */
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

/** Returns an error message, or null when the file looks acceptable. UX only. */
export function validatePdf(file: { name: string; type: string; size: number }): string | null {
  const looksPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
  if (!looksPdf) return 'Only PDF files are supported.';
  if (file.size === 0) return 'The file is empty.';
  if (file.size > MAX_UPLOAD_BYTES) return `The file exceeds the ${MAX_UPLOAD_BYTES / 1024 / 1024} MB limit.`;
  return null;
}

@Injectable({ providedIn: 'root' })
export class KnowledgeService {
  private readonly http = inject(HttpClient);

  list(limit = 50, offset = 0): Observable<DocumentPage> {
    const params = new HttpParams().set('limit', limit).set('offset', offset);
    return this.http.get<DocumentPage>('/api/knowledge/documents', { params });
  }

  upload(file: File): Observable<KnowledgeDocument> {
    const body = new FormData();
    body.append('file', file, file.name);
    return this.http.post<KnowledgeDocument>('/api/knowledge/documents', body);
  }

  delete(id: string): Observable<void> {
    return this.http.delete<void>(`/api/knowledge/documents/${encodeURIComponent(id)}`);
  }

  loadSamples(): Observable<SampleLoadResult> {
    return this.http.post<SampleLoadResult>('/api/knowledge/documents/load-samples', {});
  }

  search(query: string, k = 5): Observable<SearchResponse> {
    return this.http.post<SearchResponse>('/api/rag/search', { query, k });
  }
}
