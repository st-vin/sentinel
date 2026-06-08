"use client";

import { useEffect, useState } from "react";
import { api, AuditRun } from "@/lib/api";
import { scoreColour, scoreLabel, moduleDisplayName } from "@/lib/utils";

export default function HistoryPage() {
  const [runs, setRuns] = useState<AuditRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .listAudits()
      .then((d) => setRuns(d.runs))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brand-primary">Audit History</h1>
          <p className="text-sm text-gray-500 mt-1">All past audit runs, most recent first.</p>
        </div>
        <a
          href="/"
          className="text-sm bg-brand-primary text-white px-4 py-2 rounded-lg hover:bg-blue-900 transition-colors font-medium"
        >
          + New Audit
        </a>
      </div>

      {loading && (
        <div className="text-center py-16 text-gray-400">
          <div className="inline-block w-6 h-6 border-4 border-brand-accent border-t-transparent rounded-full animate-spin mb-3" />
          <div className="text-sm">Loading audit history…</div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm mb-4">
          {error}
        </div>
      )}

      {!loading && runs.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <div className="text-4xl mb-3">📋</div>
          <div className="font-medium">No audits yet</div>
          <div className="text-sm mt-1">
            <a href="/" className="text-brand-accent hover:underline">Run your first audit →</a>
          </div>
        </div>
      )}

      {!loading && runs.length > 0 && (
        <div className="space-y-3">
          {runs.map((run) => (
            <a
              key={run.run_id}
              href={`/audit/${run.run_id}`}
              className="flex items-center gap-4 bg-white border border-gray-200 rounded-xl px-5 py-4 hover:border-brand-accent hover:shadow-sm transition-all group"
            >
              {/* Score */}
              <div className="flex-none text-center w-16">
                {run.overall_score != null ? (
                  <>
                    <div
                      className="text-2xl font-bold"
                      style={{ color: scoreColour(run.overall_score) }}
                    >
                      {run.overall_score}
                    </div>
                    <div
                      className="text-xs font-medium"
                      style={{ color: scoreColour(run.overall_score) }}
                    >
                      {scoreLabel(run.overall_score)}
                    </div>
                  </>
                ) : (
                  <div className="text-gray-400 text-sm font-medium">—</div>
                )}
              </div>

              <div className="w-px h-10 bg-gray-200 flex-none" />

              {/* Details */}
              <div className="flex-1 min-w-0">
                <div className="font-medium text-gray-800 text-sm truncate">{run.target_endpoint}</div>
                <div className="flex items-center gap-2 mt-1 flex-wrap">
                  <span className="text-xs font-mono text-gray-400">{run.run_id.slice(0, 8)}…</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                    run.status === "complete" ? "bg-green-100 text-green-700"
                    : run.status === "partial" ? "bg-amber-100 text-amber-700"
                    : run.status === "failed" ? "bg-red-100 text-red-700"
                    : "bg-gray-100 text-gray-600"
                  }`}>
                    {run.status}
                  </span>
                  {run.modules.map((m) => (
                    <span key={m} className="text-xs bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded">
                      {moduleDisplayName(m)}
                    </span>
                  ))}
                </div>
              </div>

              <span className="flex-none text-gray-300 group-hover:text-brand-accent text-lg transition-colors">→</span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
