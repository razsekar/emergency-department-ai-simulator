import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { COMPARISON_HISTORY, comparisonRun } from '../testing/demo-fixtures';
import { ComparisonService } from './comparison.service';

describe('ComparisonService', () => {
  let service: ComparisonService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(ComparisonService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('posts the selections and optional question', () => {
    service.run({ selections: [{ provider: 'ollama', model: 'a' }, { provider: 'ollama', model: 'b' }] }).subscribe();
    const req = http.expectOne('/api/comparison/run');
    expect(req.request.method).toBe('POST');
    expect(req.request.body.selections.length).toBe(2);
    expect('question' in req.request.body).toBe(false); // backend defaults to the fixed question
    req.flush(comparisonRun());
  });

  it('pages the history', () => {
    service.runs(10, 20).subscribe();
    const req = http.expectOne((r) => r.url === '/api/comparison/runs');
    expect(req.request.params.get('limit')).toBe('10');
    expect(req.request.params.get('offset')).toBe('20');
    req.flush(COMPARISON_HISTORY);
  });

  it('loads one comparison by id (encoded)', () => {
    service.detail('abc/1').subscribe();
    http.expectOne('/api/comparison/runs/abc%2F1').flush(comparisonRun());
  });
});
