import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';
import { me, updateMe } from '@/api/auth';
import {
  anonymizeAccountPii,
  cancelAccountDeletion,
  confirmIrreversibleDeletion,
  exportUserPiiJson,
  GdprAuditLogItem,
  getGdprAuditLogs,
  requestAccountDeletion,
} from '@/api/gdpr';
import { clearRefreshToken, clearToken, setCurrency } from '@/lib/auth';

const SUPPORTED_CURRENCIES = [
  { code: 'INR', label: 'Indian Rupee (INR)' },
  { code: 'USD', label: 'US Dollar (USD)' },
  { code: 'EUR', label: 'Euro (EUR)' },
  { code: 'GBP', label: 'British Pound (GBP)' },
  { code: 'AED', label: 'UAE Dirham (AED)' },
  { code: 'SGD', label: 'Singapore Dollar (SGD)' },
  { code: 'AUD', label: 'Australian Dollar (AUD)' },
  { code: 'CAD', label: 'Canadian Dollar (CAD)' },
  { code: 'JPY', label: 'Japanese Yen (JPY)' },
];

export default function Account() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [currency, setCurrencyState] = useState('INR');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [pendingToken, setPendingToken] = useState<string | null>(null);
  const [scheduledFor, setScheduledFor] = useState<string | null>(null);
  const [auditLogs, setAuditLogs] = useState<GdprAuditLogItem[]>([]);
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const refreshAuditTrail = async () => {
    try {
      const res = await getGdprAuditLogs();
      setAuditLogs(res.audit_logs);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await me();
        setEmail(data.email);
        setCurrencyState(data.preferred_currency || 'INR');
        await refreshAuditTrail();
      } catch (error: unknown) {
        const message =
          error instanceof Error ? error.message : 'Failed to load account';
        toast({ title: 'Failed to load account', description: message });
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [toast]);

  const onSave = async () => {
    setSaving(true);
    try {
      const updated = await updateMe({ preferred_currency: currency });
      setCurrency(updated.preferred_currency);
      toast({
        title: 'Account updated',
        description: `Default currency set to ${updated.preferred_currency}.`,
      });
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : 'Failed to update account';
      toast({ title: 'Failed to update account', description: message });
    } finally {
      setSaving(false);
    }
  };

  const handleExportJson = async () => {
    setExporting(true);
    try {
      const pkg = await exportUserPiiJson();
      const blob = new Blob([JSON.stringify(pkg, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `finmind_gdpr_export_${pkg.subject_hash.slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      await refreshAuditTrail();
      toast({
        title: 'GDPR Data Export Ready',
        description: `Exported package (SHA-256: ${pkg.sha256_checksum.slice(0, 12)}...).`,
      });
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : 'Failed to export personal data';
      toast({ title: 'Export failed', description: message });
    } finally {
      setExporting(false);
    }
  };

  const handleScheduleDeletion = async () => {
    if (!passwordConfirm) {
      toast({ title: 'Password required', description: 'Enter your password to verify identity.' });
      return;
    }
    setDeleting(true);
    try {
      const res = await requestAccountDeletion({ password: passwordConfirm, grace_days: 30 });
      setPendingToken(res.confirmation_token);
      setScheduledFor(res.scheduled_for);
      await refreshAuditTrail();
      toast({
        title: 'Account deletion scheduled',
        description: `Scheduled for ${res.scheduled_for}. Confirm below for immediate erasure.`,
      });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Deletion request failed';
      toast({ title: 'Error', description: message });
    } finally {
      setDeleting(false);
    }
  };

  const handleCancelDeletion = async () => {
    try {
      await cancelAccountDeletion();
      setPendingToken(null);
      setScheduledFor(null);
      await refreshAuditTrail();
      toast({ title: 'Deletion cancelled', description: 'Your account remains active.' });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Cancel failed';
      toast({ title: 'Error', description: message });
    }
  };

  const handleAnonymize = async () => {
    if (!passwordConfirm) {
      toast({ title: 'Password required', description: 'Enter your password to anonymize PII.' });
      return;
    }
    try {
      const res = await anonymizeAccountPii(passwordConfirm);
      setEmail(res.anonymized_email);
      await refreshAuditTrail();
      toast({ title: 'PII Anonymized', description: 'Personal identifiers scrubbed.' });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Anonymization failed';
      toast({ title: 'Error', description: message });
    }
  };

  const handleIrreversibleDelete = async () => {
    setDeleting(true);
    try {
      await confirmIrreversibleDeletion({
        password: passwordConfirm || undefined,
        confirmation_token: pendingToken || undefined,
      });
      clearToken();
      clearRefreshToken();
      toast({
        title: 'Account permanently deleted',
        description: 'All personal data has been irreversibly erased.',
      });
      navigate('/signin');
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Permanent deletion failed';
      toast({ title: 'Error', description: message });
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="page-wrap space-y-6">
      <div className="page-header">
        <div className="relative">
          <h1 className="page-title">Account & Privacy Settings</h1>
          <p className="page-subtitle">
            Manage profile defaults and GDPR Article 15/17 data export & erasure controls.
          </p>
        </div>
      </div>

      <div className="card card-interactive space-y-5 fade-in-up">
        {loading ? (
          <div className="text-sm text-muted-foreground">Loading account...</div>
        ) : (
          <>
            <div className="space-y-2">
              <Label>Email</Label>
              <div className="input bg-muted/30">{email}</div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="preferred_currency">Preferred Currency</Label>
              <select
                id="preferred_currency"
                className="input"
                value={currency}
                onChange={(e) => setCurrencyState(e.target.value)}
              >
                {SUPPORTED_CURRENCIES.map((item) => (
                  <option key={item.code} value={item.code}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex justify-end">
              <Button
                variant="financial"
                onClick={onSave}
                disabled={saving || loading}
              >
                {saving ? 'Saving...' : 'Save Preferences'}
              </Button>
            </div>
          </>
        )}
      </div>

      <div className="card space-y-5 p-6">
        <div>
          <h2 className="text-lg font-bold">GDPR Privacy & Data Controls</h2>
          <p className="text-sm text-muted-foreground">
            Export a portable archive of all your personal data or execute an irreversible account deletion with full compliance audit logging.
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <Button variant="outline" onClick={() => void handleExportJson()} disabled={exporting}>
            {exporting ? 'Preparing Export...' : 'Export Personal Data (JSON)'}
          </Button>
        </div>

        <div className="space-y-3 border-t pt-4">
          <Label htmlFor="gdpr_password">Confirm Password for Sensitive Privacy Actions</Label>
          <input
            id="gdpr_password"
            type="password"
            className="input"
            placeholder="Enter current password"
            value={passwordConfirm}
            onChange={(e) => setPasswordConfirm(e.target.value)}
          />
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" onClick={() => void handleAnonymize()} disabled={deleting}>
              Anonymize Personal Identifiers
            </Button>
            <Button variant="outline" onClick={() => void handleScheduleDeletion()} disabled={deleting}>
              Request Account Deletion (30-Day Grace)
            </Button>
            {scheduledFor && (
              <Button variant="outline" onClick={() => void handleCancelDeletion()}>
                Cancel Scheduled Deletion
              </Button>
            )}
            <Button variant="destructive" onClick={() => void handleIrreversibleDelete()} disabled={deleting}>
              Execute Immediate Irreversible Deletion
            </Button>
          </div>
        </div>

        {auditLogs.length > 0 && (
          <div className="space-y-2 border-t pt-4">
            <h3 className="text-sm font-semibold">GDPR Compliance Audit Trail</h3>
            <div className="space-y-1.5 text-xs">
              {auditLogs.map((log) => (
                <div key={log.id} className="flex items-center justify-between rounded border px-3 py-2">
                  <span className="font-mono font-semibold">{log.action}</span>
                  <span className="text-muted-foreground">{log.created_at}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
