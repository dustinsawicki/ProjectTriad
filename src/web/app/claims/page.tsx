"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";

type ClaimRow = {
  claim_id: string;
  claim_number: string;
  loss_type: string;
  status: string;
  reported_amount: number | null;
  reserve_amount: number | null;
  settled_amount: number | null;
  assigned_adjuster: string | null;
  created_utc: string;
  top_fraud_score: number | null;
  route: string | null;
};

const STATUSES = ["", "open", "triaged", "assessed", "settled", "denied"];
const ROUTES   = ["", "stp", "desk", "field", "siu"];

const statusStyle: Record<string, string> = {
  open:     "bg-sky-50 text-sky-700 ring-1 ring-sky-200",
  triaged:  "bg-indigo-50 text-indigo-700 ring-1 ring-indigo-200",
  assessed: "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
  settled:  "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
  denied:   "bg-red-50 text-red-700 ring-1 ring-red-200",
};

export default function ClaimsQueue() {
  const [status, setStatus] = useState("");
  const [route, setRoute]   = useState("");
  const [minFraud, setMinFraud] = useState("");

  const q = useQuery({
    queryKey: ["queue", status, route, minFraud],
    queryFn: () => {
      const p = new URLSearchParams();
      if (status)  p.set("status", status);
      if (route)   p.set("route", route);
      if (minFraud) p.set("min_fraud_score", minFraud);
      return api<ClaimRow[]>(`/api/queue?${p.toString()}`);
    }
  });

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Claims Queue</h1>
          <p className="text-sm text-slate-400 mt-0.5">{q.data ? `${q.data.length} claims` : "Loading…"}</p>
        </div>
        <div className="flex gap-3 text-sm">
          <label className="flex flex-col gap-1">
            <span className="text-slate-400 text-xs font-medium">Status</span>
            <select className="border border-slate-200 rounded-lg px-3 py-1.5 bg-white shadow-sm focus:ring-2 focus:ring-sky-200 focus:border-sky-400 outline-none"
              value={status} onChange={(e) => setStatus(e.target.value)}>
              {STATUSES.map((s) => <option key={s} value={s}>{s || "All"}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-slate-400 text-xs font-medium">Route</span>
            <select className="border border-slate-200 rounded-lg px-3 py-1.5 bg-white shadow-sm focus:ring-2 focus:ring-sky-200 focus:border-sky-400 outline-none"
              value={route} onChange={(e) => setRoute(e.target.value)}>
              {ROUTES.map((r) => <option key={r} value={r}>{r || "All"}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-slate-400 text-xs font-medium">Min Fraud</span>
            <input type="number" min="0" max="1" step="0.05"
              className="border border-slate-200 rounded-lg px-3 py-1.5 w-20 bg-white shadow-sm focus:ring-2 focus:ring-sky-200 focus:border-sky-400 outline-none"
              value={minFraud} onChange={(e) => setMinFraud(e.target.value)} />
          </label>
        </div>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500 text-left text-xs uppercase tracking-wider">
            <tr>
              <th className="px-4 py-3">Claim</th>
              <th className="px-4 py-3">Loss Type</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Route</th>
              <th className="px-4 py-3 text-right">Fraud</th>
              <th className="px-4 py-3 text-right">Reported</th>
              <th className="px-4 py-3 text-right">Settled</th>
              <th className="px-4 py-3">Adjuster</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {q.isLoading && <tr><td className="px-4 py-12 text-center text-slate-400" colSpan={8}>
              <div className="flex items-center justify-center gap-2">
                <div className="w-4 h-4 rounded-full border-2 border-sky-200 border-t-sky-500 animate-spin" />
                Loading claims…
              </div>
            </td></tr>}
            {q.isError && <tr><td className="px-4 py-8 text-center text-red-600" colSpan={8}>{String(q.error)}</td></tr>}
            {q.data?.map((c) => (
              <tr key={c.claim_id} className="hover:bg-sky-50/50 transition-colors">
                <td className="px-4 py-3 font-mono text-sm">
                  <Link className="text-sky-600 hover:text-sky-800 hover:underline font-medium" href={`/claims/${c.claim_id}`}>{c.claim_number}</Link>
                </td>
                <td className="px-4 py-3 text-slate-600">{c.loss_type}</td>
                <td className="px-4 py-3">
                  <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${statusStyle[c.status] ?? "bg-slate-50 text-slate-700"}`}>
                    {c.status}
                  </span>
                </td>
                <td className="px-4 py-3 uppercase text-xs tracking-wide font-medium">
                  {c.route === "siu"
                    ? <span className="bg-red-500 text-white px-2.5 py-1 rounded-full text-xs font-semibold">SIU</span>
                    : <span className="text-slate-500">{c.route ?? "—"}</span>}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {c.top_fraud_score != null ? (
                    <span className={`font-medium ${c.top_fraud_score > 0.7 ? "text-red-600" : c.top_fraud_score > 0.4 ? "text-amber-600" : "text-slate-500"}`}>
                      {c.top_fraud_score.toFixed(2)}
                    </span>
                  ) : <span className="text-slate-300">—</span>}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-slate-600">
                  {c.reported_amount != null ? `$${c.reported_amount.toLocaleString()}` : "—"}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-slate-600">
                  {c.settled_amount  != null ? `$${c.settled_amount.toLocaleString()}` : "—"}
                </td>
                <td className="px-4 py-3 text-slate-400 text-xs">{c.assigned_adjuster ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
