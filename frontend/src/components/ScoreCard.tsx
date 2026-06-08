"use client";

import { scoreColour, scoreLabel, moduleDisplayName } from "@/lib/utils";

interface ScoreCardProps {
  moduleId: string;
  score: number;
  findingCount: number;
  status: string;
}

export function ScoreCard({ moduleId, score, findingCount, status }: ScoreCardProps) {
  const colour = scoreColour(score);
  const label = scoreLabel(score);

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 text-center shadow-sm">
      <div className="text-3xl font-bold" style={{ color: colour }}>
        {status === "failed" ? "—" : score}
      </div>
      <div className="text-xs text-gray-400 mb-1">/100</div>
      <div className="text-xs font-bold" style={{ color: colour }}>
        {status === "failed" ? "ERROR" : label}
      </div>
      <div className="text-xs font-semibold text-gray-600 mt-2 leading-tight">
        {moduleDisplayName(moduleId)}
      </div>
      <div className="text-xs text-gray-400 mt-1">{findingCount} finding{findingCount !== 1 ? "s" : ""}</div>
    </div>
  );
}
