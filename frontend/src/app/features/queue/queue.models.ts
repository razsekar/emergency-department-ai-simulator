/** Typed mirrors of backend/app/modules/patient_queue/application/contracts.py. */

export type VisitStatus = 'waiting' | 'in_treatment' | 'discharged';
export type TriageCategory = 'critical' | 'urgent' | 'semi_urgent' | 'non_urgent';
export type InvestigationStatus = 'none' | 'pending' | 'completed';

export interface QueueRow {
  visit_ref: string;
  patient_ref: string;
  arrival_at: string;
  registered_at: string | null;
  department_code: string;
  triage_category: TriageCategory;
  status: VisitStatus;
  waiting_minutes: number;
  assigned_staff_ref: string | null;
  bed_ref: string | null;
  investigation_status: InvestigationStatus;
  discharged_at: string | null;
}

export interface QueuePage {
  items: QueueRow[];
  total: number;
  page: number;
  page_size: number;
  as_of: string | null;
}

export interface QueueQuery {
  status?: VisitStatus | '';
  department?: string;
  triage_category?: TriageCategory | '';
  investigation_status?: InvestigationStatus | '';
  min_wait_minutes?: number | null;
  max_wait_minutes?: number | null;
  arrived_within_minutes?: number | null;
  page?: number;
  page_size?: number;
}

export interface PendingInvestigationItem {
  visit_ref: string;
  patient_ref: string;
  department_code: string;
  facility_code: string;
  requested_at: string;
  age_minutes: number;
  expected_minutes: number;
  delay_minutes: number;
}

export interface FacilityPending {
  facility_code: string;
  pending: number;
  avg_age_minutes: number;
}

export interface PendingInvestigations {
  as_of: string | null;
  pending_count: number;
  avg_age_minutes: number;
  max_age_minutes: number;
  avg_delay_minutes: number;
  by_facility: FacilityPending[];
  items: PendingInvestigationItem[];
}

export interface WaitBucket {
  label: string;
  min_minutes: number;
  max_minutes: number | null;
  count: number;
}

export interface WaitingMetrics {
  as_of: string | null;
  waiting_patients: number;
  avg_wait_minutes: number;
  max_wait_minutes: number;
  distribution: WaitBucket[];
}
