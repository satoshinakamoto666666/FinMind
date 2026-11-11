import { apiClient } from "./client";

export interface JobStats {
  total: number;
  pending: number;
  retrying: number;
  sent: number;
  dead_letter: number;
  success_rate_pct: number;
  retry_policy: {
    base_delay_minutes: number;
    backoff_factor: number;
    max_retries: number;
    schedule_minutes: number[];
  };
}

export interface JobRunRecord {
  id: number;
  job_name: string;
  status: string;
  processed_count: number;
  succeeded_count: number;
  retried_count: number;
  dead_letter_count: number;
  duration_ms: number;
  started_at: string;
  finished_at: string;
}

export interface DeadLetterItem {
  id: number;
  bill_id: number | null;
  message: string;
  channel: string;
  send_at: string;
  retry_count: number;
  max_retries: number;
  last_error: string | null;
  last_retry_at: string | null;
  retry_status: string;
}

export async function fetchJobsStatus() {
  const res = await apiClient.get<{
    scheduler_status: string;
    stats: JobStats;
    recent_runs: JobRunRecord[];
  }>("/jobs/status");
  return res.data;
}

export async function triggerRemindersJob() {
  const res = await apiClient.post("/jobs/reminders/run");
  return res.data;
}

export async function fetchDeadLetters() {
  const res = await apiClient.get<DeadLetterItem[]>("/jobs/dead-letters");
  return res.data;
}

export async function resetDeadLetter(reminderId: number) {
  const res = await apiClient.post(`/jobs/dead-letters/${reminderId}/reset`);
  return res.data;
}
