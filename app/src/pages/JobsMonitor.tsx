import React, { useEffect, useState } from "react";
import {
  DeadLetterItem,
  JobRunRecord,
  JobStats,
  fetchDeadLetters,
  fetchJobsStatus,
  resetDeadLetter,
  triggerRemindersJob,
} from "../api/jobs";

export default function JobsMonitor() {
  const [status, setStatus] = useState<string>("healthy");
  const [stats, setStats] = useState<JobStats | null>(null);
  const [runs, setRuns] = useState<JobRunRecord[]>([]);
  const [deadLetters, setDeadLetters] = useState<DeadLetterItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [statusData, dlData] = await Promise.all([
        fetchJobsStatus(),
        fetchDeadLetters(),
      ]);
      setStatus(statusData.scheduler_status);
      setStats(statusData.stats);
      setRuns(statusData.recent_runs);
      setDeadLetters(dlData);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const handleRunNow = async () => {
    await triggerRemindersJob();
    await loadAll();
  };

  const handleReset = async (id: number) => {
    await resetDeadLetter(id);
    await loadAll();
  };

  if (loading && !stats) {
    return <div className="p-6">Loading background job telemetry...</div>;
  }

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Background Job Retry & Monitoring</h1>
          <p className="text-sm text-gray-500">
            Exponential backoff ({stats?.retry_policy.schedule_minutes.join("m → ")}m) with dead-letter recovery
          </p>
        </div>
        <button
          onClick={handleRunNow}
          className="px-4 py-2 rounded bg-indigo-600 text-white font-medium hover:bg-indigo-700"
        >
          Run Due Jobs Now
        </button>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="p-4 rounded border bg-white">
            <div className="text-xs text-gray-500">Status</div>
            <div className="text-lg font-semibold uppercase">{status}</div>
          </div>
          <div className="p-4 rounded border bg-white">
            <div className="text-xs text-gray-500">Pending</div>
            <div className="text-lg font-semibold">{stats.pending}</div>
          </div>
          <div className="p-4 rounded border bg-white">
            <div className="text-xs text-gray-500">Retrying</div>
            <div className="text-lg font-semibold text-amber-600">{stats.retrying}</div>
          </div>
          <div className="p-4 rounded border bg-white">
            <div className="text-xs text-gray-500">Dead Letter</div>
            <div className="text-lg font-semibold text-red-600">{stats.dead_letter}</div>
          </div>
          <div className="p-4 rounded border bg-white">
            <div className="text-xs text-gray-500">Success Rate</div>
            <div className="text-lg font-semibold text-emerald-600">{stats.success_rate_pct}%</div>
          </div>
        </div>
      )}

      <div className="rounded border bg-white p-4">
        <h2 className="text-lg font-semibold mb-3">Dead-Letter Queue ({deadLetters.length})</h2>
        {deadLetters.length === 0 ? (
          <p className="text-sm text-gray-500">No permanently failed jobs in the dead-letter queue.</p>
        ) : (
          <div className="space-y-2">
            {deadLetters.map((item) => (
              <div key={item.id} className="flex items-center justify-between border rounded p-3">
                <div>
                  <div className="font-medium">{item.message}</div>
                  <div className="text-xs text-red-600">
                    Retries: {item.retry_count}/{item.max_retries} • Error: {item.last_error || "Dispatch failed"}
                  </div>
                </div>
                <button
                  onClick={() => handleReset(item.id)}
                  className="px-3 py-1 rounded bg-gray-900 text-white text-xs"
                >
                  Reset & Retry
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded border bg-white p-4">
        <h2 className="text-lg font-semibold mb-3">Recent Execution History</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead>
              <tr className="border-b text-gray-500">
                <th className="py-2">Run ID</th>
                <th>Status</th>
                <th>Processed</th>
                <th>Succeeded</th>
                <th>Retried</th>
                <th>Dead-Lettered</th>
                <th>Duration</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className="border-b">
                  <td className="py-2">#{r.id}</td>
                  <td>{r.status}</td>
                  <td>{r.processed_count}</td>
                  <td>{r.succeeded_count}</td>
                  <td>{r.retried_count}</td>
                  <td>{r.dead_letter_count}</td>
                  <td>{r.duration_ms} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
