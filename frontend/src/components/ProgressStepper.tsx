"use client";

import { AuditStatus } from "@/lib/api";

const STAGES = [
  { key: "planning", label: "Planning", description: "Audit plan confirmed" },
  { key: "prompt_injection", label: "Prompt Injection", description: "Adversarial probing" },
  { key: "pii_leakage", label: "PII Detection", description: "Scanning traces & logs" },
  { key: "hallucination_risk", label: "Hallucination Check", description: "Evaluating accuracy" },
  { key: "reasoning", label: "Reasoning", description: "Cross-referencing findings" },
  { key: "reporting", label: "Reporting", description: "Generating outputs" },
];

const COMPLETE_STATUSES = new Set(["complete", "partial", "failed"]);

function stageStatus(stageKey: string, currentStage: string | undefined, overallStatus: string): "done" | "active" | "error" | "pending" {
  if (overallStatus === "failed" && stageKey === currentStage) return "error";
  const stageIdx = STAGES.findIndex((s) => s.key === stageKey);
  const currentIdx = STAGES.findIndex((s) => s.key === currentStage);

  if (COMPLETE_STATUSES.has(overallStatus) && currentStage === "complete") return "done";
  if (stageIdx < currentIdx) return "done";
  if (stageIdx === currentIdx) return "active";
  return "pending";
}

interface Props {
  status: AuditStatus;
  findingsSoFar?: number;
}

export function ProgressStepper({ status, findingsSoFar = 0 }: Props) {
  const isDone = COMPLETE_STATUSES.has(status.status);

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-800 text-sm">Audit Progress</h3>
        <div className="text-xs text-gray-500">
          {findingsSoFar > 0 && (
            <span className="font-medium text-orange-600">⚠ {findingsSoFar} finding{findingsSoFar !== 1 ? "s" : ""} so far</span>
          )}
        </div>
      </div>

      <div className="space-y-2">
        {STAGES.map((stage) => {
          const s = stageStatus(stage.key, status.current_stage, status.status);
          return (
            <div key={stage.key} className="flex items-center gap-3">
              <div className="flex-none w-5 h-5 flex items-center justify-center">
                {s === "done" && <span className="text-green-600 font-bold text-sm">✓</span>}
                {s === "active" && (
                  <span className="inline-block w-3 h-3 rounded-full bg-brand-accent animate-pulse" />
                )}
                {s === "error" && <span className="text-red-600 text-sm">✕</span>}
                {s === "pending" && <span className="inline-block w-3 h-3 rounded-full bg-gray-200" />}
              </div>
              <div>
                <div className={`text-sm font-medium ${s === "active" ? "text-brand-accent" : s === "done" ? "text-green-700" : "text-gray-400"}`}>
                  {stage.label}
                </div>
                {s === "active" && (
                  <div className="text-xs text-gray-500">{stage.description}…</div>
                )}
                {s === "done" && (
                  <div className="text-xs text-gray-400">{stage.description}</div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {!isDone && (
        <div className="mt-4">
          <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-accent rounded-full transition-all duration-500"
              style={{ width: `${status.progress_pct}%` }}
            />
          </div>
          <div className="text-xs text-gray-400 text-right mt-1">{status.progress_pct}%</div>
        </div>
      )}
    </div>
  );
}
