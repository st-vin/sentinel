"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Finding } from "@/lib/api";
import { severityColour } from "@/lib/utils";

interface Props {
  findings: Finding[];
}

const SEVERITIES = ["critical", "high", "medium", "low", "info"];

export function RiskChart({ findings }: Props) {
  const data = SEVERITIES.map((sev) => ({
    name: sev.charAt(0).toUpperCase() + sev.slice(1),
    count: findings.filter((f) => f.severity === sev).length,
    colour: severityColour(sev),
  })).filter((d) => d.count > 0);

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
        No findings to display
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#6B7280" }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fontSize: 11, fill: "#9CA3AF" }} axisLine={false} tickLine={false} allowDecimals={false} />
        <Tooltip
          contentStyle={{ fontSize: 12, border: "1px solid #E5E7EB", borderRadius: 8, boxShadow: "0 2px 8px rgba(0,0,0,0.08)" }}
          formatter={(value: number) => [`${value} finding${value !== 1 ? "s" : ""}`, ""]}
        />
        <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={48}>
          {data.map((entry, index) => (
            <Cell key={index} fill={entry.colour} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
