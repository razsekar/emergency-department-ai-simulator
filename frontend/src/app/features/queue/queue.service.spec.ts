import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { toParams } from '../resources/resources.service';
import { formatWait } from './queue.page';
import { QueueService } from './queue.service';

describe('QueueService', () => {
  let http: HttpTestingController;
  let service: QueueService;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(QueueService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('maps every filter to the backend query parameter and omits empty ones', () => {
    service
      .list({
        status: 'waiting',
        department: 'ACUTE',
        triage_category: '',
        investigation_status: 'pending',
        min_wait_minutes: 10,
        max_wait_minutes: null,
        arrived_within_minutes: 120,
        page: 2,
        page_size: 25,
      })
      .subscribe();
    const req = http.expectOne((r) => r.url === '/api/patient-queue');
    const p = req.request.params;
    expect(p.get('status')).toBe('waiting');
    expect(p.get('department')).toBe('ACUTE');
    expect(p.get('investigation_status')).toBe('pending');
    expect(p.get('min_wait_minutes')).toBe('10');
    expect(p.get('arrived_within_minutes')).toBe('120');
    expect(p.get('page')).toBe('2');
    expect(p.get('page_size')).toBe('25');
    expect(p.has('triage_category')).toBe(false);
    expect(p.has('max_wait_minutes')).toBe(false);
    req.flush({ items: [], total: 0, page: 2, page_size: 25, as_of: null });
  });

  it('keeps a zero minimum wait (0 is a real filter value)', () => {
    service.list({ min_wait_minutes: 0 }).subscribe();
    const req = http.expectOne((r) => r.url === '/api/patient-queue');
    expect(req.request.params.get('min_wait_minutes')).toBe('0');
    req.flush({ items: [], total: 0, page: 1, page_size: 50, as_of: null });
  });

  it('fetches waiting metrics and pending investigations', () => {
    service.waitingMetrics('MINOR', 60).subscribe();
    const w = http.expectOne((r) => r.url === '/api/patient-queue/waiting-metrics');
    expect(w.request.params.get('department')).toBe('MINOR');
    expect(w.request.params.get('window_minutes')).toBe('60');
    w.flush({ as_of: null, waiting_patients: 0, avg_wait_minutes: 0, max_wait_minutes: 0, distribution: [] });

    service.pendingInvestigations(undefined, 10).subscribe();
    const p = http.expectOne((r) => r.url === '/api/patient-queue/pending-investigations');
    expect(p.request.params.get('limit')).toBe('10');
    p.flush({ as_of: null, pending_count: 0, avg_age_minutes: 0, max_age_minutes: 0, avg_delay_minutes: 0, by_facility: [], items: [] });
  });
});

describe('helpers', () => {
  it('toParams drops undefined, null and empty strings', () => {
    const p = toParams({ a: 'x', b: undefined, c: null, d: '', e: 0 });
    expect(p.keys().sort()).toEqual(['a', 'e']);
  });

  it('formatWait renders minutes and hours', () => {
    expect(formatWait(15.4)).toBe('15 min');
    expect(formatWait(75)).toBe('1 h 15 min');
  });
});
