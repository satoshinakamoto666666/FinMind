import { apiRequest } from './client';

export interface DigestCategoryBreakdown {
  category_id: number | null;
  category_name: string;
  amount: number;
  previous_amount: number;
  change_amount: number;
  change_pct: number | null;
  percentage: number;
  trend: 'UP' | 'DOWN' | 'FLAT' | 'NEW' | 'GONE';
}

export interface DigestDailyBreakdown {
  date: string;
  day_name: string;
  spent: number;
  income: number;
  transaction_count: number;
}

export interface DigestUpcomingBill {
  id: number;
  name: string;
  amount: number;
  currency: string;
  next_due_date: string;
  autopay_enabled: boolean;
}

export interface WeeklyDigestResponse {
  week: string;
  week_start: string;
  week_end: string;
  previous_week: string;
  currency: string;
  total_spent: number;
  total_income: number;
  net_flow: number;
  daily_average: number;
  transaction_count: number;
  expense_count: number;
  previous_week_spent: number;
  week_over_week_change: number;
  week_over_week_change_pct: number | null;
  category_breakdown: DigestCategoryBreakdown[];
  daily_breakdown: DigestDailyBreakdown[];
  upcoming_bills: DigestUpcomingBill[];
  trends: {
    overall_direction: string;
    top_category: { category_name: string; amount: number; percentage: number } | null;
    biggest_increase: { category_name: string; change_amount: number; change_pct: number | null } | null;
    biggest_decrease: { category_name: string; change_amount: number; change_pct: number | null } | null;
    highest_spend_day: { date: string; day_name: string; spent: number } | null;
  };
  insights: string[];
  method: string;
}

export async function getWeeklyDigest(params?: { week?: string; currency?: string }): Promise<WeeklyDigestResponse> {
  const qs = new URLSearchParams();
  if (params?.week) qs.set('week', params.week);
  if (params?.currency) qs.set('currency', params.currency);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return apiRequest<WeeklyDigestResponse>(`/digest/weekly${suffix}`);
}

export async function sendWeeklyDigestNotification(payload?: {
  week?: string;
  channel?: 'email' | 'whatsapp';
  currency?: string;
}): Promise<{ reminder_id: number; channel: string; week: string; message: string; status: string }> {
  return apiRequest('/digest/weekly/send', {
    method: 'POST',
    body: JSON.stringify(payload ?? {}),
  });
}
