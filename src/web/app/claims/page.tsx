"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  type ClaimRow,
  ROUTE_ORDER,
  STATUS_ORDER,
  formatCurrency,
  formatLossType,
  formatPercent,
  formatRoute,
  formatStatus
} from "@/lib/claims";

const STATUS_BADGES: Record<string, string> = {
  open: "bg-blue-50 text-blue-700 ring-blue-200/80",
  triaged: "bg-amber-50 text-amber-700 ring-amber-200/80",
  assessed: "bg-slate-100 text-slate-700 ring-slate-200/80",
  settled: "bg-emerald-50 text-emerald-700 ring-emerald-200/80",
  denied: "bg-rose-50 text-rose-700 ring-rose-200/80"
};

const ROUTE_BADGES: Record<string, string> = {
  stp: "bg-accent/10 text-amber-800 ring-accent/20",
  desk: "bg-blue-50 text-blue-700 ring-blue-200/80",
  field: "bg-emerald-50 text-emerald-700 ring-emerald-200/80",
  siu: "bg-violet-50 text-violet-700 ring-violet-200/80"
};

function selectClassName() {
  return "h-11 rounded-2xl border border-slate-200/80 bg-white/90 px-3 text-sm text-slate-700 shadow-sm shadow-slate-900/5 focus:border-accent";
}

export default function ClaimsQueue() {
  const [status, setStatus] = useState("");
  const [route, setRoute] = useState("");
  const [minFraud, setMinFraud] = useState("");

  const q = useQuery({
    queryKey: ["queue", status, route, minFraud],
    queryFn: () => {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      if (route) params.set("route", route);
      if (minFraud) params.set("min_fraud_score", minFraud);
      const queryString = params.toString();
      return api<ClaimRow[]>(queryString ? `/api/queue?${queryString}` : "/api/queue");
    }
  });

  const claims = q.data ?? [];

  return (
    <div className="space-y-6">
      <section className="rounded-[30px] border border-white/70 bg-[linear-gradient(135deg,rgba(255,255,255,0.92),rgba(244,247,251,0.86))] p-6 shadow-[0_20px_60px_rgba(16,34,62,0.08)] backdrop-blur lg:p-7">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-accent">Claims operations</p>
            <h1 className="mt-2 text-4xl font-semibold text-navy">Claims queue</h1>
            <p className="mt-3 max-w-2xl text-sm text-slate-500">
              Monitor intake, route handling, fraud posture, and financial exposure across the live claims backlog.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3 xl:min-w-[560px]">
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">Status</span>
              <select className={selectClassName()} value={status} onChange={(event) => setStatus(event.target.value)}>
                <option value="">Any status</option>
                {STATUS_ORDER.map((option) => (
                  <option key={option} value={option}>
                    {formatStatus(option)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">Route</span>
              <select className={selectClassName()} value={route} onChange={(event) => setRoute(event.target.value)}>
                <option value="">Any route</option>
                {ROUTE_ORDER.map((option) => (
                  <option key={option} value={option}>
                    {formatRoute(option)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">Min fraud score</span>
              <input
                type="number"
                min="0"
                max="1"
                step="0.05"
                className={selectClassName()}
                value={minFraud}
                onChange={(event) => setMinFraud(event.target.value)}
                placeholder="0.70"
              />
            </label>
          </div>
        </div>
      </section>

      <section className="overflow-hidden rounded-[30px] border border-white/70 bg-white/85 shadow-[0_20px_60px_rgba(16,34,62,0.08)] backdrop-blur">
        <div className="flex flex-col gap-3 border-b border-slate-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.9),rgba(248,250,252,0.84))] px-6 py-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-semibold text-navy">Queue inventory</h2>
              <span className="rounded-full bg-accent/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-amber-800">
                {claims.length} visible
              </span>
            </div>
            <p className="mt-2 text-sm text-slate-500">
              Refined view of every claim currently returned by the queue API.
            </p>
          </div>
          <div className="text-sm text-slate-500">
            {q.dataUpdatedAt > 0 ? `Updated ${new Date(q.dataUpdatedAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}` : "Awaiting data"}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-[1120px] w-full text-sm">
            <thead className="bg-slate-50/90 text-left text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
              <tr>
                <th className="px-4 py-3">Claim</th>
                <th className="px-4 py-3">Loss type</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Route</th>
                <th className="px-4 py-3 text-right">Fraud</th>
                <th className="px-4 py-3 text-right">Reported</th>
                <th className="px-4 py-3 text-right">Reserve</th>
                <th className="px-4 py-3 text-right">Settled</th>
                <th className="px-4 py-3">Adjuster</th>
                <th className="px-4 py-3">Created</th>
              </tr>
            </thead>
            <tbody>
              {q.isLoading ? (
                <tr>
                  <td className="px-4 py-12 text-center text-slate-400" colSpan={10}>
                    Loading claims…
                  </td>
                </tr>
              ) : null}
              {q.isError ? (
                <tr>
                  <td className="px-4 py-12 text-center text-red-600" colSpan={10}>
                    {String(q.error)}
                  </td>
                </tr>
              ) : null}
              {!q.isLoading && !q.isError && claims.length === 0 ? (
                <tr>
                  <td className="px-4 py-12 text-center text-slate-400" colSpan={10}>
                    No claims matched the current filters.
                  </td>
                </tr>
              ) : null}
              {claims.map((claim) => (
                <tr
                  key={claim.ClaimId}
                  className="border-t border-slate-200/70 odd:bg-white even:bg-slate-50/65 hover:-translate-y-px hover:bg-ice/45"
                >
                  <td className="px-4 py-3 font-mono text-[13px] text-navy">
                    <Link className="inline-flex items-center gap-2 font-semibold hover:text-blue-700" href={`/claims/${claim.ClaimId}`}>
                      {claim.ClaimNumber}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-700">{formatLossType(claim.LossType)}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${STATUS_BADGES[claim.Status] ?? "bg-slate-100 text-slate-700 ring-slate-200/80"}`}>
                      {formatStatus(claim.Status)}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {claim.route ? (
                      <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.18em] ring-1 ${ROUTE_BADGES[claim.route] ?? "bg-slate-100 text-slate-700 ring-slate-200/80"}`}>
                        {claim.route}
                      </span>
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-medium tabular-nums text-slate-700">
                    {formatPercent(claim.top_fraud_score)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-700">{formatCurrency(claim.ReportedAmount)}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-700">{formatCurrency(claim.ReserveAmount)}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-700">{formatCurrency(claim.SettledAmount)}</td>
                  <td className="px-4 py-3 text-slate-500">{claim.AssignedAdjuster ?? "—"}</td>
                  <td className="px-4 py-3 text-slate-500">
                    {new Date(claim.CreatedUtc).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
