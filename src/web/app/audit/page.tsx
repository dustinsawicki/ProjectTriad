"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

type Audit = {
  event_id: string;
  actor: string;
  actor_name: string;
  action: string;
  outcome: string;
  rationale: Record<string, unknown> | null;
  created_utc: string;
};

export default function AuditPage() {
  const q = useQuery({ queryKey: ["audit"], queryFn: () => api<Audit[]>("/api/audit?limit=200") });
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Audit Log</h1>
        <p className="text-sm text-slate-400 mt-0.5">{q.data ? `${q.data.length} events` : "Loading…"}</p>
      </div>
      <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500 text-xs uppercase tracking-wider">
            <tr>
              <th className="px-4 py-3">When</th>
              <th className="px-4 py-3">Actor</th>
              <th className="px-4 py-3">Action</th>
              <th className="px-4 py-3">Outcome</th>
              <th className="px-4 py-3">Rationale</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {q.isLoading && <tr><td className="px-4 py-12 text-center text-slate-400" colSpan={5}>
              <div className="flex items-center justify-center gap-2">
                <div className="w-4 h-4 rounded-full border-2 border-sky-200 border-t-sky-500 animate-spin" />
                Loading audit events…
              </div>
            </td></tr>}
            {q.data?.map((a) => (
              <tr key={a.event_id} className="hover:bg-sky-50/50 transition-colors">
                <td className="px-4 py-3 font-mono text-xs text-slate-400">{new Date(a.created_utc).toLocaleString()}</td>
                <td className="px-4 py-3">
                  <span className="font-medium text-slate-700">{a.actor_name}</span>
                  <span className="text-xs text-slate-400 ml-1">({a.actor})</span>
                </td>
                <td className="px-4 py-3 text-slate-600">{a.action}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                    a.outcome === "block"
                      ? "bg-red-50 text-red-700 ring-1 ring-red-200"
                      : "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200"
                  }`}>
                    {a.outcome}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-slate-500 max-w-xs truncate">
                  {a.rationale
                    ? <code className="bg-slate-50 px-2 py-0.5 rounded text-xs">{JSON.stringify(a.rationale)}</code>
                    : <span className="text-slate-300">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
