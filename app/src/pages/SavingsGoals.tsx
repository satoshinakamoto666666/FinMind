import React, { useEffect, useState } from 'react';
import {
  SavingsGoal,
  contributeToSavingsGoal,
  createSavingsGoal,
  deleteSavingsGoal,
  listSavingsGoals,
} from '@/api/savingsGoals';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';

export const SavingsGoals: React.FC = () => {
  const [goals, setGoals] = useState<SavingsGoal[]>([]);
  const [name, setName] = useState('');
  const [targetAmount, setTargetAmount] = useState('');
  const [targetDate, setTargetDate] = useState('');
  const [contributionAmounts, setContributionAmounts] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(false);

  const loadGoals = async () => {
    setLoading(true);
    try {
      const data = await listSavingsGoals();
      setGoals(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadGoals();
  }, []);

  const handleCreateGoal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !targetAmount) return;
    await createSavingsGoal({
      name: name.trim(),
      target_amount: Number(targetAmount),
      target_date: targetDate || undefined,
    });
    setName('');
    setTargetAmount('');
    setTargetDate('');
    await loadGoals();
  };

  const handleContribute = async (goalId: number) => {
    const raw = contributionAmounts[goalId];
    if (!raw || Number(raw) <= 0) return;
    await contributeToSavingsGoal(goalId, { amount: Number(raw) });
    setContributionAmounts((prev) => ({ ...prev, [goalId]: '' }));
    await loadGoals();
  };

  const handleDelete = async (goalId: number) => {
    await deleteSavingsGoal(goalId);
    await loadGoals();
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Savings Goals & Milestones</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Create New Savings Goal</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleCreateGoal} className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Input
              placeholder="Goal name (e.g. Emergency Fund)"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <Input
              type="number"
              placeholder="Target amount"
              value={targetAmount}
              onChange={(e) => setTargetAmount(e.target.value)}
            />
            <Input
              type="date"
              value={targetDate}
              onChange={(e) => setTargetDate(e.target.value)}
            />
            <Button type="submit">Create Goal</Button>
          </form>
        </CardContent>
      </Card>

      {loading && <p className="text-sm text-muted-foreground">Loading savings goals...</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {goals.map((goal) => (
          <Card key={goal.id} data-testid={`savings-goal-${goal.id}`}>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>{goal.name}</CardTitle>
                <p className="text-sm text-muted-foreground">
                  {goal.currency} {goal.current_amount.toLocaleString()} /{' '}
                  {goal.target_amount.toLocaleString()} ({goal.progress_percentage}%)
                </p>
              </div>
              <Badge variant={goal.status === 'COMPLETED' ? 'default' : 'secondary'}>
                {goal.status}
              </Badge>
            </CardHeader>
            <CardContent className="space-y-4">
              <Progress value={goal.progress_percentage} />

              <div className="space-y-1">
                <p className="text-xs font-semibold uppercase text-muted-foreground">
                  Milestones
                </p>
                <div className="flex flex-wrap gap-2">
                  {goal.milestones.map((m) => (
                    <Badge
                      key={m.id}
                      variant={m.reached ? 'default' : 'outline'}
                      data-testid={`milestone-${m.id}`}
                    >
                      {m.reached ? '✓ ' : ''}
                      {m.title} ({goal.currency} {m.target_amount})
                    </Badge>
                  ))}
                </div>
              </div>

              <div className="flex gap-2">
                <Input
                  type="number"
                  placeholder="Contribution amount"
                  value={contributionAmounts[goal.id] ?? ''}
                  onChange={(e) =>
                    setContributionAmounts((prev) => ({
                      ...prev,
                      [goal.id]: e.target.value,
                    }))
                  }
                />
                <Button type="button" onClick={() => void handleContribute(goal.id)}>
                  Add Savings
                </Button>
                <Button
                  type="button"
                  variant="destructive"
                  onClick={() => void handleDelete(goal.id)}
                >
                  Delete
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
};

export default SavingsGoals;
