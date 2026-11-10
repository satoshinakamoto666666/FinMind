import { api } from './client';

export type SavingsMilestone = {
  id: number;
  goal_id: number;
  title: string;
  target_amount: number;
  percentage?: number;
  reached: boolean;
  reached_at?: string | null;
};

export type SavingsContribution = {
  id: number;
  goal_id: number;
  amount: number;
  notes?: string | null;
  contributed_at: string;
};

export type SavingsGoal = {
  id: number;
  name: string;
  target_amount: number;
  current_amount: number;
  remaining_amount: number;
  progress_percentage: number;
  currency: string;
  target_date?: string | null;
  category?: string | null;
  notes?: string | null;
  status: 'ACTIVE' | 'COMPLETED' | 'PAUSED';
  milestones: SavingsMilestone[];
  contributions?: SavingsContribution[];
  newly_unlocked_milestones?: SavingsMilestone[];
  created_at: string;
};

export type SavingsGoalCreate = {
  name: string;
  target_amount: number;
  current_amount?: number;
  currency?: string;
  target_date?: string;
  category?: string;
  notes?: string;
  auto_milestones?: boolean;
};

export async function listSavingsGoals(status?: string): Promise<SavingsGoal[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : '';
  return api<SavingsGoal[]>(`/savings-goals${qs}`);
}

export async function createSavingsGoal(payload: SavingsGoalCreate): Promise<SavingsGoal> {
  return api<SavingsGoal>('/savings-goals', { method: 'POST', body: payload });
}

export async function contributeToSavingsGoal(
  goalId: number,
  payload: { amount: number; notes?: string; contributed_at?: string }
): Promise<SavingsGoal> {
  return api<SavingsGoal>(`/savings-goals/${goalId}/contribute`, {
    method: 'POST',
    body: payload,
  });
}

export async function addSavingsMilestone(
  goalId: number,
  payload: { title: string; target_amount: number }
): Promise<SavingsMilestone> {
  return api<SavingsMilestone>(`/savings-goals/${goalId}/milestones`, {
    method: 'POST',
    body: payload,
  });
}

export async function deleteSavingsGoal(goalId: number): Promise<{ message: string }> {
  return api<{ message: string }>(`/savings-goals/${goalId}`, { method: 'DELETE' });
}
