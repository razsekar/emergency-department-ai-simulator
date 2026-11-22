import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';
import { KnowledgeService, MAX_UPLOAD_BYTES, validatePdf } from './knowledge.service';

describe('validatePdf', () => {
  it('accepts a PDF by mime type or extension', () => {
    expect(validatePdf({ name: 'a.pdf', type: 'application/pdf', size: 10 })).toBeNull();
    expect(validatePdf({ name: 'A.PDF', type: '', size: 10 })).toBeNull();
  });
  it('rejects other types, empty files and oversize files', () => {
    expect(validatePdf({ name: 'a.txt', type: 'text/plain', size: 10 })).toMatch(/PDF/);
    expect(validatePdf({ name: 'a.pdf', type: 'application/pdf', size: 0 })).toMatch(/empty/);
    expect(validatePdf({ name: 'a.pdf', type: 'application/pdf', size: MAX_UPLOAD_BYTES + 1 })).toMatch(/limit/);
  });
});

describe('KnowledgeService', () => {
  function setup() {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    return { svc: TestBed.inject(KnowledgeService), http: TestBed.inject(HttpTestingController) };
  }

  it('lists documents with paging params', () => {
    const { svc, http } = setup();
    svc.list(10, 20).subscribe();
    const req = http.expectOne((r) => r.url === '/api/knowledge/documents');
    expect(req.request.params.get('limit')).toBe('10');
    expect(req.request.params.get('offset')).toBe('20');
  });

  it('uploads as multipart form data', () => {
    const { svc, http } = setup();
    svc.upload(new File(['%PDF-1.4'], 'x.pdf', { type: 'application/pdf' })).subscribe();
    const req = http.expectOne('/api/knowledge/documents');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toBeInstanceOf(FormData);
    expect((req.request.body as FormData).get('file')).toBeInstanceOf(File);
  });

  it('searches and deletes against the right endpoints', () => {
    const { svc, http } = setup();
    svc.search('wait time', 3).subscribe();
    const search = http.expectOne('/api/rag/search');
    expect(search.request.body).toEqual({ query: 'wait time', k: 3 });
    svc.delete('a/b').subscribe();
    expect(http.expectOne('/api/knowledge/documents/a%2Fb').request.method).toBe('DELETE');
  });
});
