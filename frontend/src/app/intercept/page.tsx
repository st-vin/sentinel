// app/intercept/page.tsx
"use client";
import React, { useEffect, useState } from "react";
import { startInterceptSession, getInterceptStatus, stopInterceptSession } from "@/lib/api";

interface Session {
  session_id: string;
  proxy_port: number;
  proxy_base_url: string;
  status: string;
  transactions_processed: number;
  blocked_count: number;
  redacted_count: number;
}

export default function InterceptPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [newUrl, setNewUrl] = useState("");

  const refresh = async () => {
    // In a real app, we would fetch a list endpoint; here we just poll existing sessions stored locally.
    // Placeholder: no list API yet.
  };

  const createSession = async () => {
    if (!newUrl) return;
    const resp = await startInterceptSession({ upstream_llm_url: newUrl });
    setSessions([...sessions, { ...resp, status: "starting", transactions_processed: 0, blocked_count: 0, redacted_count: 0 }]);
    setNewUrl("");
  };

  const stopSession = async (id: string) => {
    await stopInterceptSession(id);
    setSessions(sessions.filter(s => s.session_id !== id));
  };

  useEffect(() => {
    const interval = setInterval(() => {
      sessions.forEach(async s => {
        const status = await getInterceptStatus(s.session_id);
        setSessions(prev => prev.map(p => (p.session_id === s.session_id ? { ...p, ...status } : p)));
      });
    }, 5000);
    return () => clearInterval(interval);
  }, [sessions]);

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Interception Sessions</h1>
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          placeholder="Upstream LLM URL (e.g. https://api.openai.com/v1)"
          value={newUrl}
          onChange={e => setNewUrl(e.target.value)}
          className="flex-1 px-3 py-2 border rounded bg-white/5 backdrop-blur-sm"
        />
        <button onClick={createSession} className="px-4 py-2 bg-brand-accent text-white rounded hover:opacity-90">
          Start Session
        </button>
      </div>
      <div className="space-y-4">
        {sessions.map(s => (
          <div key={s.session_id} className="p-4 border rounded bg-white/5 backdrop-blur-sm">
            <div className="flex justify-between items-center mb-2">
              <span className="font-mono text-sm">{s.session_id}</span>
              <button onClick={() => stopSession(s.session_id)} className="text-sm text-red-400 hover:underline">
                Stop
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>Status: <span className={s.status === "running" ? "text-green-400" : "text-yellow-400"}>{s.status}</span></div>
              <div>Port: {s.proxy_port}</div>
              <div>Processed: {s.transactions_processed}</div>
              <div>Blocked: {s.blocked_count}</div>
              <div>Redacted: {s.redacted_count}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
