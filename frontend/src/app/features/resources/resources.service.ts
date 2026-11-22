import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  BedAvailability,
  BedFilter,
  BedRow,
  DepartmentCapacity,
  Facility,
  Page,
  StaffAvailability,
  StaffFilter,
  StaffRole,
  StaffRow,
} from './resources.models';

/** Builds query params, omitting undefined/empty values. */
export function toParams(values: Record<string, string | number | undefined | null>): HttpParams {
  let p = new HttpParams();
  for (const [k, v] of Object.entries(values)) {
    if (v !== undefined && v !== null && v !== '') p = p.set(k, String(v));
  }
  return p;
}

@Injectable({ providedIn: 'root' })
export class ResourceService {
  private readonly http = inject(HttpClient);

  bedAvailability(department?: string): Observable<BedAvailability> {
    return this.http.get<BedAvailability>('/api/resources/beds/availability', {
      params: toParams({ department }),
    });
  }

  staffAvailability(department?: string, role?: StaffRole): Observable<StaffAvailability> {
    return this.http.get<StaffAvailability>('/api/resources/staff/availability', {
      params: toParams({ department, role }),
    });
  }

  departments(): Observable<DepartmentCapacity[]> {
    return this.http.get<DepartmentCapacity[]>('/api/resources/departments');
  }

  facilities(): Observable<Facility[]> {
    return this.http.get<Facility[]>('/api/resources/facilities');
  }

  beds(f: BedFilter = {}): Observable<Page<BedRow>> {
    return this.http.get<Page<BedRow>>('/api/resources/beds', {
      params: toParams({ department: f.department, status: f.status, page: f.page, page_size: f.pageSize }),
    });
  }

  staff(f: StaffFilter = {}): Observable<Page<StaffRow>> {
    return this.http.get<Page<StaffRow>>('/api/resources/staff', {
      params: toParams({
        department: f.department,
        role: f.role,
        status: f.status,
        page: f.page,
        page_size: f.pageSize,
      }),
    });
  }
}
