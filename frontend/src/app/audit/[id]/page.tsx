"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { api, AuditReport, AuditStatus, Finding } from "@/lib/api";
import { ScoreCard } from "@/components/ScoreCard";
import { FindingList } from "@/components/FindingList";
import { ProgressStepper } from "@/components/ProgressStepper";
import { RiskChart } from "@/components/RiskChart";
import { scoreColour, scoreLabel, formatDate } from "@/lib/utils";

const POLL_INTERVAL_MS = 4000;
const TERMINAL_STATUSES = new Set(["complete", "partial", "failed"]);

export default function AuditPage() {
  const params = useParams();
  const runId = params.id as string;

  const [status, setStatus] = useState<AuditStatus | null>(null);
  const [report, setReport] = useState<AuditReport | null>(null);
  const [sevFilter, setSevFilter] = useState("all");
  const [error, setError] = useState("");

  const fetchStatus = useCallback(async () => {
    try {
      const s = await api.getStatus(runId);
      setStatus(s);
      return s;
    } catch (e: any) {
      setError(e.message);
      return null;
    }
  }, [runId]);

  const fetchReport = useCallback(async () => {
    try {
      const r = await api.getFullReport(runId);
      setReport(r);
    } catch {
      // not yet available
    }
  }, [runId]);

  useEffect(() => {
    let interval: NodeJS.Timeout;

    const poll = async () => {
      const s = await fetchStatus();
      if (s && TERMINAL_STATUSES.has(s.status)) {
        clearInterval(interval);
        await fetchReport();
      }
    };

    poll();
    interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchStatus, fetchReport]);

  const allFindings: Finding[] = report
    ? report.modules.flatMap((m) => m.findings)
    : [];

  const criticalCount = allFindings.filter((f) => f.severity === "critical").length;
  const highCount = allFindings.filter((f) => f.severity === "high").length;
  const mediumCount = allFindings.filter((f) => f.severity === "medium").length;

  const isDone = status && TERMINAL_STATUSES.has(status.status);

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      {/* Page header */}
      <div className="flex items-start justify-between mb-6 flex-wrap gap-3">
        <div>
          <div className="text-xs font-mono text-gray-400 mb-1">Audit #{runId.slice(0, 8)}…</div>
          <h1 className="text-2xl font-bold text-brand-primary">
            {isDone ? "Audit Results" : "Audit in Progress…"}
          </h1>
          {report && (
            <div className="text-sm text-gray-500 mt-1">
              {report.target_agent.endpoint} — {formatDate(report.created_at)}
            </div>
          )}
        </div>

        {isDone && report && (
          <div className="flex gap-2">
            <a
              href={api.getPdfUrl(runId)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 bg-brand-primary text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-blue-900 transition-colors"
            >
              ↓ PDF Report
            </a>
            <a
              href={api.getJsonUrl(runId)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 border border-gray-300 text-gray-700 text-sm font-medium px-4 py-2 rounded-lg hover:border-brand-accent hover:text-brand-accent transition-colors"
            >
              ↓ JSON
            </a>
          </div>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm mb-6">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column — progress or overall score */}
        <div className="space-y-4">
          {/* Progress stepper — always visible while running */}
          {status && !isDone && (
            <ProgressStepper status={status} findingsSoFar={status.findings_so_far} />
          )}

          {/* Overall score — shown after completion */}
          {isDone && report && (
            <div className="bg-white border border-gray-200 rounded-xl p-6 text-center shadow-sm">
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                Overall Compliance Score
              </div>
              <div
                className="text-6xl font-bold leading-none"
                style={{ color: scoreColour(report.overall_score) }}
              >
                {report.overall_score}
              </div>
              <div className="text-sm text-gray-400 mt-1">/100</div>
              <div
                className="text-sm font-bold mt-2"
                style={{ color: scoreColour(report.overall_score) }}
              >
                {scoreLabel(report.overall_score)}
              </div>
              <div
                className={`mt-3 text-xs px-3 py-1 rounded-full inline-block font-medium ${
                  report.status === "complete"
                    ? "bg-green-100 text-green-700"
                    : report.status === "partial"
                    ? "bg-amber-100 text-amber-700"
                    : "bg-red-100 text-red-700"
                }`}
              >
                {report.status.toUpperCase()}
              </div>
            </div>
          )}

          {/* Severity breakdown chart */}
          {isDone && allFindings.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                Findings by Severity
              </div>
              <RiskChart findings={allFindings} />
              <div className="grid grid-cols-2 gap-2 mt-3 text-xs">
                {criticalCount > 0 && (
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-red-600 flex-none" />
                    <span className="text-gray-600">{criticalCount} Critical</span>
                  </div>
                )}
                {highCount > 0 && (
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-orange-600 flex-none" />
                    <span className="text-gray-600">{highCount} High</span>
                  </div>
                )}
                {mediumCount > 0 && (
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-500 flex-none" />
                    <span className="text-gray-600">{mediumCount} Medium</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right column — module scores + findings */}
        <div className="lg:col-span-2 space-y-4">
          {/* Module score cards */}
          {isDone && report && report.modules.length > 0 && (
            <div className={`grid gap-3 grid-cols-${Math.min(report.modules.length, 3)}`}
              style={{ gridTemplateColumns: `repeat(${Math.min(report.modules.length, 3)}, 1fr)` }}
            >
              {report.modules.map((mod) => (
                <ScoreCard
                  key={mod.module_id}
                  moduleId={mod.module_id}
                  score={mod.score}
                  findingCount={mod.findings.length}
                  status={mod.status}
                />
              ))}
            </div>
          )}

          {/* Live findings feed (during run) */}
          {!isDone && status && status.findings_so_far > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                Live Findings Feed
              </div>
              <div className="text-sm text-gray-500 animate-pulse">
                {status.findings_so_far} finding{status.findings_so_far !== 1 ? "s" : ""} detected…
              </div>
            </div>
          )}

          {/* Findings list (after completion) */}
          {isDone && allFindings.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between flex-wrap gap-2">
                <div className="font-semibold text-gray-800 text-sm">
                  Findings ({allFindings.length})
                </div>
                <div className="flex gap-1.5 text-xs">
                  {(["all", "critical", "high", "medium", "low"] as const).map((sev) => (
                    <button
                      key={sev}
                      onClick={() => setSevFilter(sev)}
                      className={`px-2.5 py-1 rounded-full font-medium transition-colors capitalize ${
                        sevFilter === sev
                          ? "bg-brand-primary text-white"
                          : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                      }`}
                    >
                      {sev === "all"
                        ? `All (${allFindings.length})`
                        : `${sev} (${allFindings.filter((f) => f.severity === sev).length})`}
                    </button>
                  ))}
                </div>
              </div>
              <div className="p-4">
                <FindingList findings={allFindings} filter={sevFilter} />
              </div>
            </div>
          )}

          {isDone && allFindings.length === 0 && (
            <div className="bg-green-50 border border-green-200 rounded-xl p-8 text-center shadow-sm">
              <div className="text-4xl mb-3">✓</div>
              <div className="font-semibold text-green-800">All Checks Passed</div>
              <div className="text-sm text-green-600 mt-1">
                No compliance issues were detected for this agent.
              </div>
            </div>
          )}

          {!isDone && !error && (
            <div className="bg-white border border-gray-200 rounded-xl p-8 text-center shadow-sm">
              <div className="inline-block w-8 h-8 border-4 border-brand-accent border-t-transparent rounded-full animate-spin mb-4" />
              <div className="text-sm text-gray-600 font-medium">
                Sentinel is auditing your agent…
              </div>
              <div className="text-xs text-gray-400 mt-1">
                Results will appear here automatically. This usually takes 1–3 minutes.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
