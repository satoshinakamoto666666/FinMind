import { apiClient } from "./client";

export interface AccountSummary {
  id: number;
  name: string;
  account_type: string;
  institution: string | null;
  currency: string;
  initial_balance: number;
  current_balance: number;
  balance_in_base_currency: number;
  base_currency: string;
  monthly_income: number;
  monthly_expenses: number;
  monthly_net_flow: number;
  share_pct: number;
  transaction_count: number;
}

export interface MultiAccountOverview {
  period: { month: string };
  base_currency: string;
  consolidated: {
    account_count: number;
    total_assets: number;
    total_liabilities: number;
    net_worth: number;
    monthly_income: number;
    monthly_expenses: number;
    monthly_net_flow: number;
    unassigned_net_flow: number;
  };
  accounts: AccountSummary[];
  recent_transactions: Array<{
    id: number;
    account_id: number | null;
    account_name: string;
    description: string;
    amount: number;
    currency: string;
    type: string;
    date: string;
  }>;
}

export async function fetchMultiAccountOverview(month?: string, accountId?: number) {
  const params: Record<string, string | number> = {};
  if (month) params.month = month;
  if (accountId) params.account_id = accountId;
  const res = await apiClient.get<MultiAccountOverview>("/dashboard/multi-account", { params });
  return res.data;
}

export async function createFinancialAccount(payload: {
  name: string;
  account_type: string;
  institution?: string;
  currency?: string;
  initial_balance?: number;
}) {
  const res = await apiClient.post("/accounts", payload);
  return res.data;
}

export async function createAccountTransfer(payload: {
  from_account_id: number;
  to_account_id: number;
  amount: number;
  notes?: string;
}) {
  const res = await apiClient.post("/accounts/transfers", payload);
  return res.data;
}
