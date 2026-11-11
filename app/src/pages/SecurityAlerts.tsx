import React, { useEffect, useState } from "react";
import {
  LoginEventItem,
  SecurityAlertItem,
  acknowledgeSecurityAlert,
  fetchLoginHistory,
  fetchLoginStats,
  fetchSecurityAlerts,
} from "../api/security";

export default function SecurityAlerts() {
  const [alerts, setAlerts] = useState<SecurityAlertItem[]>([]);
  const [events, setEvents] = useState<LoginEventItem[]>([]);
  const [stats, setStats] = useState<any>(null);

  const loadAll = async () => {
    const [a, e, s] = await Promise.all([
      fetchSecurityAlerts(),
      fetchLoginHistory(),
      fetchLoginStats(),
    ]);
    setAlerts(a);
    setEvents(e);
    setStats(s);
  };

  useEffect(() => {
    loadAll();
  }, []);

  const handleAck = async (id: number) => {
    await acknowledgeSecurityAlert(id);
    await loadAll();
  };

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold">Login Anomaly Detection & Security Alerts</h1>
        <p className="text-sm text-gray-500">
          Real-time monitoring for new IP addresses, unrecognized devices, impossible travel, and brute-force bursts
        </p>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded border bg-white">
            <div className="text-xs text-gray-500">Unacknowledged Alerts</div>
            <div className="text-xl font-bold text-red-600">{stats.unacknowledged_alerts}</div>
          </div>
          <div className="p-4 rounded border bg-white">
            <div className="text-xs text-gray-500">Suspicious Logins</div>
            <div className="text-xl font-semibold text-amber-600">{stats.suspicious_events}</div>
          </div>
          <div className="p-4 rounded border bg-white">
            <div className="text-xs text-gray-500">Failed Attempts</div>
            <div className="text-xl font-semibold">{stats.failed_logins}</div>
          </div>
          <div className="p-4 rounded border bg-white">
            <div className="text-xs text-gray-500">Trusted Devices</div>
            <div className="text-xl font-semibold text-emerald-600">{stats.trusted_devices_count}</div>
          </div>
        </div>
      )}

      <div className="p-4 rounded border bg-white space-y-3">
        <h2 className="font-semibold">Suspicious Activity Alerts</h2>
        {alerts.length === 0 ? (
          <p className="text-sm text-gray-500">No suspicious login alerts recorded.</p>
        ) : (
          alerts.map((a) => (
            <div
              key={a.id}
              className="flex items-center justify-between p-3 rounded border"
            >
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold px-2 py-0.5 rounded bg-red-100 text-red-700">
                    {a.severity}
                  </span>
                  <span className="font-medium">{a.message}</span>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  Reasons: {a.reasons.join(", ")} • {a.created_at}
                </div>
              </div>
              {!a.acknowledged && (
                <button
                  onClick={() => handleAck(a.id)}
                  className="px-3 py-1 rounded bg-gray-900 text-white text-xs"
                >
                  Acknowledge
                </button>
              )}
            </div>
          ))
        )}
      </div>

      <div className="p-4 rounded border bg-white">
        <h2 className="font-semibold mb-3">Login Event History</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead>
              <tr className="border-b text-gray-500">
                <th className="py-2">Time</th>
                <th>IP Address</th>
                <th>Country</th>
                <th>Result</th>
                <th>Risk Score</th>
                <th>Reasons</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev) => (
                <tr key={ev.id} className="border-b">
                  <td className="py-2">{ev.created_at}</td>
                  <td>{ev.ip_address}</td>
                  <td>{ev.country_code || "-"}</td>
                  <td>{ev.success ? "SUCCESS" : "FAILED"}</td>
                  <td>{ev.risk_score}</td>
                  <td>{ev.reasons.join(", ") || "Baseline"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
