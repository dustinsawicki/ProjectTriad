"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

type Audit = {
  EventId: string;
  Actor: string;
  ActorName: string;
  Action: string;
  Outcome: string;
  RationaleJson: Record<string, unknown> | null;
  CorrelationId: string | null;
  CreatedUtc: string;
};

export default function AuditPage() {
  const q = useQuery({ queryKey: ["audit"], queryFn: () => api<Audit[]>("/api/audit?limit=200") });
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-navy">Audit log</h1>
      {q.data && <p className="text-sm text-slate-500">{q.data.length} events</p>}
      <div className="bg-white rounded-2xl border border-white/70 shadow-[0_20px_60px_rgba(16,34,62,0.08)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-600 border-b">
            <tr>
              <th className="px-4 py-3 font-medium">When</th>
              <th className="px-4 py-3 font-medium">Actor</th>
              <th className="px-4 py-3 font-medium">Action</th>
              <th className="px-4 py-3 font-medium">Outcome</th>
              <th className="px-4 py-3 font-medium">Rationale</th>
            </tr>
          </thead>
          <tbody>
            {q.data?.map((a) => (
              <tr key={a.EventId} className="border-t border-slate-100 hover:bg-slate-50/60 transition-colors">
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{new Date(a.CreatedUtc).toLocaleString()}</td>
                <td className="px-4 py-3">{a.ActorName} <span className="text-xs text-slate-400">({a.Actor})</span></td>
                <td className="px-4 py-3 font-mono text-xs">{a.Action}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    a.Outcome === "block" ? "bg-red-100 text-red-700" :
                    a.Outcome === "flag" ? "bg-amber-100 text-amber-700" :
                    "bg-emerald-100 text-emerald-700"
                  }`}>
                    {a.Outcome}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-slate-600 max-w-xs truncate">
                  {a.RationaleJson ? <code className="bg-slate-100 px-1.5 py-0.5 rounded">{JSON.stringify(a.RationaleJson)}</code> : <span className="text-slate-400">--</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
