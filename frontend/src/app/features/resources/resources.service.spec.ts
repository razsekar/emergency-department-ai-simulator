import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ResourceService } from './resources.service';

describe('ResourceService', () => {
  let http: HttpTestingController;
  let service: ResourceService;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(ResourceService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('queries bed availability, optionally by department', () => {
    service.bedAvailability().subscribe();
    const all = http.expectOne('/api/resources/beds/availability');
    all.flush({ total_beds: 0, occupied_beds: 0, available_beds: 0, utilization_pct: 0, by_department: [] });

    service.bedAvailability('PEDS').subscribe();
    const one = http.expectOne((r) => r.url === '/api/resources/beds/availability');
    expect(one.request.params.get('department')).toBe('PEDS');
    one.flush({ total_beds: 0, occupied_beds: 0, available_beds: 0, utilization_pct: 0, by_department: [] });
  });

  it('queries staff availability by role and department', () => {
    service.staffAvailability('ACUTE', 'nurse').subscribe();
    const req = http.expectOne((r) => r.url === '/api/resources/staff/availability');
    expect(req.request.params.get('department')).toBe('ACUTE');
    expect(req.request.params.get('role')).toBe('nurse');
    req.flush({ on_duty: 0, available: 0, busy: 0, totals_by_role: [], groups: [] });
  });

  it('pages beds and staff with backend parameter names', () => {
    service.beds({ status: 'available', page: 3, pageSize: 50 }).subscribe();
    const b = http.expectOne((r) => r.url === '/api/resources/beds');
    expect(b.request.params.get('status')).toBe('available');
    expect(b.request.params.get('page')).toBe('3');
    expect(b.request.params.get('page_size')).toBe('50');
    b.flush({ items: [], total: 0, page: 3, page_size: 50 });

    service.staff({ role: 'doctor', status: 'busy' }).subscribe();
    const s = http.expectOne((r) => r.url === '/api/resources/staff');
    expect(s.request.params.get('role')).toBe('doctor');
    expect(s.request.params.get('status')).toBe('busy');
    s.flush({ items: [], total: 0, page: 1, page_size: 50 });
  });

  it('lists departments and facilities', () => {
    service.departments().subscribe();
    http.expectOne('/api/resources/departments').flush([]);
    service.facilities().subscribe();
    http.expectOne('/api/resources/facilities').flush([]);
  });
});
