export function scoreColour(score: number): string {
  if (score >= 90) return "#15803D";
  if (score >= 75) return "#16A34A";
  if (score >= 60) return "#D97706";
  if (score >= 40) return "#EA580C";
  return "#DC2626";
}

export function scoreLabel(score: number): string {
  if (score >= 90) return "PASS";
  if (score >= 75) return "LOW RISK";
  if (score >= 60) return "MEDIUM RISK";
  if (score >= 40) return "HIGH RISK";
  return "CRITICAL RISK";
}

export function scoreBg(score: number): string {
  if (score >= 90) return "bg-green-800";
  if (score >= 75) return "bg-green-600";
  if (score >= 60) return "bg-amber-600";
  if (score >= 40) return "bg-orange-600";
  return "bg-red-600";
}

export function severityColour(severity: string): string {
  const map: Record<string, string> = {
    critical: "#DC2626",
    high: "#EA580C",
    medium: "#D97706",
    low: "#16A34A",
    info: "#6B7280",
  };
  return map[severity] ?? "#6B7280";
}

export function severityBg(severity: string): string {
  const map: Record<string, string> = {
    critical: "bg-red-600",
    high: "bg-orange-600",
    medium: "bg-amber-500",
    low: "bg-green-600",
    info: "bg-gray-500",
  };
  return map[severity] ?? "bg-gray-500";
}

export function moduleDisplayName(moduleId: string): string {
  const map: Record<string, string> = {
    prompt_injection: "Prompt Injection",
    pii_leakage: "PII Leakage",
    hallucination_risk: "Hallucination Risk",
  };
  return map[moduleId] ?? moduleId.replace(/_/g, " ");
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
}
