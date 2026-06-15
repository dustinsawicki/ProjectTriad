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
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-navy">Audit log</h1>
      <div className="bg-white rounded shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-100 text-left text-slate-600">
            <tr>
              <th className="px-3 py-2">When</th>
              <th className="px-3 py-2">Actor</th>
              <th className="px-3 py-2">Action</th>
              <th className="px-3 py-2">Outcome</th>
              <th className="px-3 py-2">Rationale</th>
            </tr>
          </thead>
          <tbody>
            {q.data?.map((a) => (
              <tr key={a.event_id} className="border-t">
                <td className="px-3 py-2 font-mono text-xs text-slate-500">{new Date(a.created_utc).toLocaleString()}</td>
                <td className="px-3 py-2">{a.actor_name} <span className="text-xs text-slate-400">({a.actor})</span></td>
                <td className="px-3 py-2">{a.action}</td>
                <td className="px-3 py-2">
                  <span className={`text-xs px-2 py-0.5 rounded ${a.outcome === "block" ? "bg-red-100 text-red-700" : "bg-emerald-100 text-emerald-700"}`}>
                    {a.outcome}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs text-slate-600">
                  {a.rationale ? <code>{JSON.stringify(a.rationale)}</code> : <span className="text-slate-400">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
