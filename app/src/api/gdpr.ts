import { apiRequest } from './client';

export interface GdprExportResponse {
  schema_version: string;
  gdpr_article: string;
  exported_at: string;
  subject_hash: string;
  sha256_checksum: string;
  record_counts: Record<string, number>;
  data: Record<string, unknown>;
}

export interface GdprAuditLogItem {
  id: number;
  user_id: number | null;
  subject_hash: string;
  action: string;
  ip_address: string | null;
  user_agent: string | null;
  details: unknown;
  created_at: string | null;
}

export async function exportUserPiiJson(): Promise<GdprExportResponse> {
  return apiRequest<GdprExportResponse>('/gdpr/export?format=json');
}

export async function requestAccountDeletion(payload: {
  password: string;
  grace_days?: number;
  reason?: string;
}): Promise<{
  request_id: number;
  status: string;
  confirmation_token: string;
  requested_at: string;
  scheduled_for: string;
  grace_days: number;
}> {
  return apiRequest('/gdpr/delete/request', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function cancelAccountDeletion(): Promise<{
  request_id: number;
  status: string;
  cancelled_at: string;
}> {
  return apiRequest('/gdpr/delete/cancel', {
    method: 'POST',
  });
}

export async function confirmIrreversibleDeletion(payload: {
  password?: string;
  confirmation_token?: string;
}): Promise<{
  status: string;
  irreversible: boolean;
  subject_hash: string;
  audit_log_id: number;
  deleted_counts: Record<string, number>;
  deleted_at: string;
}> {
  return apiRequest('/gdpr/delete/confirm', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function anonymizeAccountPii(password: string): Promise<{
  status: string;
  anonymized_email: string;
  subject_hash: string;
}> {
  return apiRequest('/gdpr/anonymize', {
    method: 'POST',
    body: JSON.stringify({ password }),
  });
}

export async function getGdprAuditLogs(): Promise<{
  audit_logs: GdprAuditLogItem[];
  count: number;
}> {
  return apiRequest('/gdpr/audit-logs');
}
