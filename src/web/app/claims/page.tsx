"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";

type ClaimRow = {
  ClaimId: string;
  ClaimNumber: string;
  LossType: string;
  Status: string;
  ReportedAmount: number | null;
  ReserveAmount: number | null;
  SettledAmount: number | null;
  AssignedAdjuster: string | null;
  CreatedUtc: string;
  top_fraud_score: number | null;
  route: string | null;
};

const STATUSES = ["", "open", "triaged", "assessed", "settled", "denied"];
const ROUTES   = ["", "stp", "desk", "field", "siu"];

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
    <div className="space-y-4">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-semibold text-navy">Claims queue</h1>
        <div className="flex gap-3 text-sm">
          <label className="flex flex-col">
            <span className="text-slate-500 text-xs">Status</span>
            <select className="border rounded px-2 py-1" value={status} onChange={(e) => setStatus(e.target.value)}>
              {STATUSES.map((s) => <option key={s} value={s}>{s || "(any)"}</option>)}
            </select>
          </label>
          <label className="flex flex-col">
            <span className="text-slate-500 text-xs">Route</span>
            <select className="border rounded px-2 py-1" value={route} onChange={(e) => setRoute(e.target.value)}>
              {ROUTES.map((r) => <option key={r} value={r}>{r || "(any)"}</option>)}
            </select>
          </label>
          <label className="flex flex-col">
            <span className="text-slate-500 text-xs">Min fraud</span>
            <input type="number" min="0" max="1" step="0.05"
              className="border rounded px-2 py-1 w-20"
              value={minFraud} onChange={(e) => setMinFraud(e.target.value)} />
          </label>
        </div>
      </div>

      <div className="bg-white rounded shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-100 text-slate-600 text-left">
            <tr>
              <th className="px-3 py-2">Claim</th>
              <th className="px-3 py-2">Loss type</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Route</th>
              <th className="px-3 py-2 text-right">Fraud</th>
              <th className="px-3 py-2 text-right">Reported</th>
              <th className="px-3 py-2 text-right">Settled</th>
              <th className="px-3 py-2">Adjuster</th>
            </tr>
          </thead>
          <tbody>
            {q.isLoading && <tr><td className="px-3 py-8 text-center text-slate-400" colSpan={8}>Loading …</td></tr>}
            {q.isError   && <tr><td className="px-3 py-8 text-center text-red-600" colSpan={8}>{String(q.error)}</td></tr>}
            {q.data?.map((c) => (
              <tr key={c.ClaimId} className="border-t hover:bg-ice/30">
                <td className="px-3 py-2 font-mono">
                  <Link className="text-navy hover:underline" href={`/claims/${c.ClaimId}`}>{c.ClaimNumber}</Link>
                </td>
                <td className="px-3 py-2">{c.LossType}</td>
                <td className="px-3 py-2">
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    c.Status === "settled" ? "bg-emerald-100 text-emerald-700"
                    : c.Status === "denied" ? "bg-red-100 text-red-700"
                    : "bg-slate-100 text-slate-700"
                  }`}>{c.Status}</span>
                </td>
                <td className="px-3 py-2 uppercase text-xs tracking-wide">
                  {c.route === "siu"
                    ? <span className="bg-accent text-white px-2 py-0.5 rounded">SIU</span>
                    : (c.route ?? "—")}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {c.top_fraud_score != null ? c.top_fraud_score.toFixed(2) : "—"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {c.ReportedAmount != null ? `$${c.ReportedAmount.toLocaleString()}` : "—"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {c.SettledAmount  != null ? `$${c.SettledAmount.toLocaleString()}` : "—"}
                </td>
                <td className="px-3 py-2 text-slate-500">{c.AssignedAdjuster ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
