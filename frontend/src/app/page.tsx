"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api, AuditRun } from "@/lib/api";
import { scoreColour, scoreLabel, formatDate } from "@/lib/utils";

const MODULES = [
  {
    id: "prompt_injection",
    label: "Prompt Injection Resistance",
    description: "Tests adversarial prompt attacks — role overrides, system prompt extraction, indirect injection.",
    frameworks: "EU AI Act Art. 15",
  },
  {
    id: "pii_leakage",
    label: "PII Leakage Detection",
    description: "Scans Arize traces and Elastic logs for personal data: email, phone, IBAN, credit card.",
    frameworks: "GDPR Art. 5, 25, 32",
  },
  {
    id: "hallucination_risk",
    label: "Hallucination / Accuracy Risk",
    description: "Evaluates factual consistency of past agent responses using Gemini as evaluator.",
    frameworks: "EU AI Act Annex III",
  },
];

export default function HomePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [recentAudits, setRecentAudits] = useState<AuditRun[]>([]);

  const [form, setForm] = useState({
    target_endpoint: "http://localhost:8001/chat",
    arize_project_id: "",
    arize_api_key: "",
    elastic_api_key: "",
    elastic_cloud_id: "",
    system_prompt: "",
    modules: ["prompt_injection", "pii_leakage", "hallucination_risk"],
    frameworks: ["gdpr", "eu_ai_act"],
  });

  useEffect(() => {
    api.listAudits().then((d) => setRecentAudits(d.runs.slice(0, 5))).catch(() => {});
  }, []);

  function toggleModule(id: string) {
    setForm((prev) => ({
      ...prev,
      modules: prev.modules.includes(id)
        ? prev.modules.filter((m) => m !== id)
        : [...prev.modules, id],
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (form.modules.length === 0) {
      setError("Please select at least one compliance module.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const result = await api.createAudit(form);
      router.push(`/audit/${result.audit_run_id}`);
    } catch (err: any) {
      setError(err.message || "Failed to start audit. Please check your configuration.");
      setLoading(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-10">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-brand-primary mb-2">Configure Your Audit</h1>
        <p className="text-gray-500">
          Point Sentinel at your AI agent, connect your observability data, and let it run a full compliance audit autonomously.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="p-6 space-y-5">
          {/* Target Agent */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">Target Agent Endpoint</label>
            <input
              type="url"
              required
              placeholder="https://your-agent-endpoint.com/chat"
              value={form.target_endpoint}
              onChange={(e) => setForm({ ...form, target_endpoint: e.target.value })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-accent focus:border-transparent"
            />
          </div>

          {/* Arize */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">Arize Project ID</label>
              <input
                type="text"
                placeholder="proj_abc123 (optional)"
                value={form.arize_project_id}
                onChange={(e) => setForm({ ...form, arize_project_id: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-accent"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">Arize API Key</label>
              <input
                type="password"
                placeholder="sk-arize-... (optional)"
                value={form.arize_api_key}
                onChange={(e) => setForm({ ...form, arize_api_key: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-accent"
              />
            </div>
          </div>

          {/* Elastic */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">Elastic Cloud ID <span className="text-gray-400 font-normal">(optional)</span></label>
              <input
                type="text"
                placeholder="my-deployment:..."
                value={form.elastic_cloud_id}
                onChange={(e) => setForm({ ...form, elastic_cloud_id: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-accent"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">Elastic API Key <span className="text-gray-400 font-normal">(optional)</span></label>
              <input
                type="password"
                placeholder="ApiKey ..."
                value={form.elastic_api_key}
                onChange={(e) => setForm({ ...form, elastic_api_key: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-accent"
              />
            </div>
          </div>

          {/* System Prompt */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">System Prompt <span className="text-gray-400 font-normal">(optional — enables deeper analysis)</span></label>
            <textarea
              rows={3}
              placeholder="You are a customer service agent for..."
              value={form.system_prompt}
              onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-accent resize-none"
            />
          </div>

          {/* Modules */}
          <div>
            <div className="text-sm font-semibold text-gray-700 mb-3">Compliance Modules</div>
            <div className="space-y-3">
              {MODULES.map((mod) => (
                <label
                  key={mod.id}
                  className={`flex items-start gap-3 p-3 rounded-lg border-2 cursor-pointer transition-colors ${
                    form.modules.includes(mod.id)
                      ? "border-brand-accent bg-blue-50"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={form.modules.includes(mod.id)}
                    onChange={() => toggleModule(mod.id)}
                    className="mt-0.5 accent-brand-accent"
                  />
                  <div>
                    <div className="font-semibold text-sm text-gray-800">{mod.label}</div>
                    <div className="text-xs text-gray-500 mt-0.5">{mod.description}</div>
                    <div className="text-xs text-brand-accent font-medium mt-1">{mod.frameworks}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
              {error}
            </div>
          )}
        </div>

        <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
          <button
            type="submit"
            disabled={loading || form.modules.length === 0}
            className="w-full bg-brand-primary hover:bg-blue-900 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-lg transition-colors text-sm tracking-wide"
          >
            {loading ? "Starting Audit..." : "▶  RUN AUDIT  (est. ~2 min)"}
          </button>
        </div>
      </form>

      {/* Recent Audits */}
      {recentAudits.length > 0 && (
        <div className="mt-10">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Recent Audits</h2>
          <div className="space-y-2">
            {recentAudits.map((run) => (
              <a
                key={run.run_id}
                href={`/audit/${run.run_id}`}
                className="flex items-center justify-between bg-white border border-gray-200 rounded-lg px-4 py-3 hover:border-brand-accent hover:shadow-sm transition-all group"
              >
                <div>
                  <div className="text-sm font-medium text-gray-800 truncate max-w-xs">{run.target_endpoint}</div>
                  <div className="text-xs text-gray-400 mt-0.5">{run.run_id.slice(0, 8)}... — {run.status}</div>
                </div>
                <div className="flex items-center gap-3">
                  {run.overall_score != null && (
                    <div className="text-right">
                      <div className="text-lg font-bold" style={{ color: scoreColour(run.overall_score) }}>
                        {run.overall_score}
                      </div>
                      <div className="text-xs" style={{ color: scoreColour(run.overall_score) }}>
                        {scoreLabel(run.overall_score)}
                      </div>
                    </div>
                  )}
                  <span className="text-brand-accent text-sm group-hover:translate-x-1 transition-transform">→</span>
                </div>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
