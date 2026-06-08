const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface AuditConfig {
  target_endpoint: string;
  arize_project_id: string;
  arize_api_key: string;
  elastic_api_key?: string;
  elastic_cloud_id?: string;
  system_prompt?: string;
  modules: string[];
  frameworks: string[];
}

export interface AuditStatus {
  audit_run_id: string;
  status: string;
  current_stage?: string;
  progress_pct: number;
  findings_so_far: number;
}

export interface Finding {
  finding_id: string;
  module_id: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  rule_id: string;
  rule_name: string;
  evidence: string;
  recommendation: string;
  confidence: number;
  description?: string;
}

export interface ModuleResult {
  module_id: string;
  score: number;
  findings: Finding[];
  status: string;
}

export interface AuditReport {
  audit_run_id: string;
  created_at: string;
  target_agent: { endpoint: string; arize_project_id: string };
  overall_score: number;
  status: string;
  modules: ModuleResult[];
  json_url?: string;
  pdf_url?: string;
}

export interface AuditRun {
  run_id: string;
  status: string;
  target_endpoint: string;
  overall_score?: number;
  modules: string[];
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error ${res.status}`);
  }
  return res.json();
}

export const api = {
  createAudit: (config: AuditConfig) =>
    apiFetch<{ audit_run_id: string; status: string; poll_url: string }>("/api/v1/audit", {
      method: "POST",
      body: JSON.stringify(config),
    }),

  getStatus: (runId: string) =>
    apiFetch<AuditStatus>(`/api/v1/audit/${runId}/status`),

  getReport: (runId: string) =>
    apiFetch<{ status: string; overall_score?: number; pdf_url?: string; json_url?: string }>(
      `/api/v1/audit/${runId}/report`
    ),

  getFullReport: (runId: string) =>
    apiFetch<AuditReport>(`/api/v1/audit/${runId}/full`),

  listAudits: () =>
    apiFetch<{ runs: AuditRun[] }>("/api/v1/audits"),

  getPdfUrl: (runId: string) => `${API_BASE}/api/v1/reports/${runId}/pdf`,
  getJsonUrl: (runId: string) => `${API_BASE}/api/v1/reports/${runId}/json`,
};
