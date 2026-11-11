import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { useToast } from '@/hooks/use-toast';
import {
  getWeeklyDigest,
  sendWeeklyDigestNotification,
  WeeklyDigestResponse,
} from '@/api/digest';
import { formatCurrency } from '@/lib/currency';

function shiftIsoWeek(isoWeek: string, deltaWeeks: number): string {
  const match = /^(\d{4})-W(\d{2})$/.exec(isoWeek);
  if (!match) return isoWeek;
  const year = Number(match[1]);
  const week = Number(match[2]);
  const jan4 = new Date(Date.UTC(year, 0, 4));
  const dayOfWeek = jan4.getUTCDay() || 7;
  const mondayWeek1 = new Date(jan4.getTime() - (dayOfWeek - 1) * 86400000);
  const targetMonday = new Date(
    mondayWeek1.getTime() + (week - 1 + deltaWeeks) * 7 * 86400000
  );
  const d = new Date(
    Date.UTC(
      targetMonday.getUTCFullYear(),
      targetMonday.getUTCMonth(),
      targetMonday.getUTCDate()
    )
  );
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const weekNo = Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  return `${d.getUTCFullYear()}-W${String(weekNo).padStart(2, '0')}`;
}

export function Digest() {
  const { toast } = useToast();
  const [week, setWeek] = useState<string | undefined>(undefined);
  const [digest, setDigest] = useState<WeeklyDigestResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [sending, setSending] = useState<boolean>(false);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      try {
        const res = await getWeeklyDigest({ week });
        if (active) {
          setDigest(res);
          if (!week) setWeek(res.week);
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Unable to load weekly digest';
        toast({ title: 'Digest error', description: msg });
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [week, toast]);

  const handleSendDigest = async () => {
    setSending(true);
    try {
      const res = await sendWeeklyDigestNotification({ week: digest?.week, channel: 'email' });
      toast({
        title: 'Weekly digest dispatched',
        description: `Sent summary for ${res.week} via ${res.channel}.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to send weekly digest';
      toast({ title: 'Notification failed', description: msg });
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="page-wrap space-y-6">
      <div className="page-header flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="page-title">Smart Weekly Financial Digest</h1>
          <p className="page-subtitle">
            Automated week-over-week spending trends, category velocity, and smart financial insights.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!digest || loading}
            onClick={() => digest && setWeek(shiftIsoWeek(digest.week, -1))}
          >
            Previous Week
          </Button>
          <span className="px-3 py-1 text-sm font-semibold rounded-md bg-secondary">
            {digest?.week || 'Current Week'}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={!digest || loading}
            onClick={() => digest && setWeek(shiftIsoWeek(digest.week, 1))}
          >
            Next Week
          </Button>
          <Button
            variant="financial"
            size="sm"
            disabled={!digest || sending}
            onClick={() => void handleSendDigest()}
          >
            {sending ? 'Sending...' : 'Email Digest'}
          </Button>
        </div>
      </div>

      {loading || !digest ? (
        <div className="card p-6 text-sm text-muted-foreground">Loading weekly summary...</div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-4">
            <div className="card p-5 space-y-1">
              <div className="text-xs text-muted-foreground">Weekly Spend ({digest.week_start} – {digest.week_end})</div>
              <div className="text-2xl font-bold">{formatCurrency(digest.total_spent, digest.currency)}</div>
              <div className="text-xs text-muted-foreground">
                Daily avg: {formatCurrency(digest.daily_average, digest.currency)}
              </div>
            </div>
            <div className="card p-5 space-y-1">
              <div className="text-xs text-muted-foreground">Week-over-Week Change</div>
              <div className="text-2xl font-bold">
                {digest.week_over_week_change >= 0 ? '+' : ''}
                {formatCurrency(digest.week_over_week_change, digest.currency)}
              </div>
              <div className="text-xs">
                <Badge variant="outline">
                  {digest.trends.overall_direction}{' '}
                  {digest.week_over_week_change_pct !== null
                    ? `(${digest.week_over_week_change_pct >= 0 ? '+' : ''}${digest.week_over_week_change_pct}%)`
                    : '(New)'}
                </Badge>
              </div>
            </div>
            <div className="card p-5 space-y-1">
              <div className="text-xs text-muted-foreground">Net Weekly Cash Flow</div>
              <div className="text-2xl font-bold">{formatCurrency(digest.net_flow, digest.currency)}</div>
              <div className="text-xs text-muted-foreground">
                Income: {formatCurrency(digest.total_income, digest.currency)}
              </div>
            </div>
            <div className="card p-5 space-y-1">
              <div className="text-xs text-muted-foreground">Top Category</div>
              <div className="text-2xl font-bold">
                {digest.trends.top_category ? digest.trends.top_category.category_name : 'None'}
              </div>
              <div className="text-xs text-muted-foreground">
                {digest.trends.top_category
                  ? `${formatCurrency(digest.trends.top_category.amount, digest.currency)} (${digest.trends.top_category.percentage}%)`
                  : 'No spend logged'}
              </div>
            </div>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            <div className="card p-6 space-y-4">
              <h2 className="text-lg font-bold">Category Breakdown & WoW Trends</h2>
              {digest.category_breakdown.length === 0 ? (
                <p className="text-sm text-muted-foreground">No category activity for this week.</p>
              ) : (
                <div className="space-y-4">
                  {digest.category_breakdown.map((cat) => (
                    <div key={cat.category_name} className="space-y-1.5">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium">{cat.category_name}</span>
                        <div className="flex items-center gap-2">
                          <span>{formatCurrency(cat.amount, digest.currency)}</span>
                          <Badge variant="secondary">
                            {cat.trend}
                            {cat.change_pct !== null ? ` ${cat.change_pct >= 0 ? '+' : ''}${cat.change_pct}%` : ''}
                          </Badge>
                        </div>
                      </div>
                      <Progress value={cat.percentage} />
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="card p-6 space-y-4">
              <h2 className="text-lg font-bold">Smart Financial Insights</h2>
              <ul className="space-y-2.5 text-sm">
                {digest.insights.map((item, idx) => (
                  <li key={idx} className="rounded-lg border border-border/60 bg-muted/20 p-3">
                    {item}
                  </li>
                ))}
              </ul>
              {digest.upcoming_bills.length > 0 && (
                <div className="pt-2 space-y-2">
                  <h3 className="text-sm font-semibold">Upcoming Bills (Next 7 Days)</h3>
                  {digest.upcoming_bills.map((bill) => (
                    <div key={bill.id} className="flex items-center justify-between text-xs border-b pb-1.5">
                      <span>{bill.name} (Due {bill.next_due_date})</span>
                      <span className="font-semibold">{formatCurrency(bill.amount, bill.currency)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default Digest;
