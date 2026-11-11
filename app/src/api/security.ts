import { apiClient } from "./client";

export interface LoginEventItem {
  id: number;
  email: string;
  ip_address: string;
  user_agent: string;
  device_fingerprint: string;
  country_code: string | null;
  success: boolean;
  risk_score: number;
  is_suspicious: boolean;
  reasons: string[];
  created_at: string;
}

export interface SecurityAlertItem {
  id: number;
  login_event_id: number | null;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  alert_type: string;
  reasons: string[];
  message: string;
  acknowledged: boolean;
  acknowledged_at: string | null;
  created_at: string;
}

export async function fetchLoginHistory(suspiciousOnly = false) {
  const res = await apiClient.get<LoginEventItem[]>("/security/login-history", {
    params: { suspicious_only: suspiciousOnly },
  });
  return res.data;
}

export async function fetchSecurityAlerts(unacknowledgedOnly = false) {
  const res = await apiClient.get<SecurityAlertItem[]>("/security/alerts", {
    params: { unacknowledged_only: unacknowledgedOnly },
  });
  return res.data;
}

export async function acknowledgeSecurityAlert(alertId: number) {
  const res = await apiClient.post<SecurityAlertItem>(
    `/security/alerts/${alertId}/acknowledge`
  );
  return res.data;
}

export async function fetchLoginStats() {
  const res = await apiClient.get<{
    total_events: number;
    successful_logins: number;
    failed_logins: number;
    suspicious_events: number;
    total_alerts: number;
    unacknowledged_alerts: number;
    trusted_devices_count: number;
  }>("/security/login-stats");
  return res.data;
}
