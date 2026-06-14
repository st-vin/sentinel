import React from 'react';

interface DashboardProps {
  status: any;
}

export default function Dashboard({ status }: DashboardProps) {
  if (!status) {
    return <div className="text-gray-400">Loading status...</div>;
  }

  const { status: sessStatus, transactions_processed, blocked_count, redacted_count } = status;

  return (
    <div className="bg-white/5 backdrop-blur-md p-4 rounded shadow-md border border-gray-200">
      <h2 className="text-lg font-semibold mb-2">Session Status</h2>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>Status: <span className={`font-bold ${sessStatus === 'running' ? 'text-green-400' : 'text-red-400'}`}>{sessStatus}</span></div>
        <div>Total Requests: {transactions_processed ?? 0}</div>
        <div>Blocked: {blocked_count ?? 0}</div>
        <div>Redacted: {redacted_count ?? 0}</div>
      </div>
    </div>
  );
}
