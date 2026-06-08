"use client";

import { useState } from "react";
import { Finding } from "@/lib/api";
import { severityBg, severityColour } from "@/lib/utils";

interface Props {
  findings: Finding[];
  filter?: string;
}

export function FindingList({ findings, filter }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showAll, setShowAll] = useState<Record<string, boolean>>({});

  const filtered = filter && filter !== "all"
    ? findings.filter((f) => f.severity === filter)
    : findings;

  if (filtered.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400">
        <div className="text-4xl mb-2">✓</div>
        <div className="text-sm font-medium">No findings in this category</div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {filtered.map((finding) => {
        const isOpen = expanded === finding.finding_id;
        const isLong = finding.evidence.length > 300;
        const showingAll = showAll[finding.finding_id];
        const displayEvidence = isLong && !showingAll
          ? finding.evidence.slice(0, 300) + "..."
          : finding.evidence;

        return (
          <div
            key={finding.finding_id}
            className="border border-gray-200 rounded-xl overflow-hidden shadow-sm"
          >
            {/* Header row — always visible */}
            <button
              onClick={() => setExpanded(isOpen ? null : finding.finding_id)}
              className="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-gray-50 transition-colors"
            >
              <span className={`inline-block px-2 py-0.5 rounded text-white text-xs font-bold uppercase flex-none mt-0.5 ${severityBg(finding.severity)}`}>
                {finding.severity}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-xs font-bold text-gray-600">[{finding.rule_id}]</span>
                  <span className="text-sm font-semibold text-gray-800">{finding.rule_name}</span>
                </div>
                <div className="text-xs text-gray-500 mt-0.5 truncate">{finding.evidence.slice(0, 120)}…</div>
              </div>
              <div className="flex-none text-xs text-gray-400 ml-2">
                {Math.round(finding.confidence * 100)}% confidence
              </div>
              <span className="flex-none text-gray-400 text-sm ml-1">{isOpen ? "▲" : "▼"}</span>
            </button>

            {/* Expanded detail */}
            {isOpen && (
              <div className="border-t border-gray-200 px-4 py-4 bg-gray-50 space-y-3">
                {finding.description && (
                  <p className="text-xs text-gray-600 leading-relaxed">{finding.description}</p>
                )}

                <div>
                  <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Evidence (Redacted)</div>
                  <div className="bg-white border border-gray-200 rounded-lg p-3 font-mono text-xs text-gray-700 break-all leading-relaxed">
                    {displayEvidence}
                    {isLong && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setShowAll((prev) => ({ ...prev, [finding.finding_id]: !showingAll }));
                        }}
                        className="block mt-1 text-brand-accent hover:underline text-xs font-sans"
                      >
                        {showingAll ? "Show less" : "Show more"}
                      </button>
                    )}
                  </div>
                </div>

                <div>
                  <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Remediation</div>
                  <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 text-xs text-gray-700 leading-relaxed">
                    {finding.recommendation}
                  </div>
                </div>

                <div className="flex gap-4 text-xs text-gray-400">
                  <span>Module: {finding.module_id.replace(/_/g, " ")}</span>
                  <span>Confidence: {Math.round(finding.confidence * 100)}%</span>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
