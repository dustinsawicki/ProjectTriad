"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  type ClaimRow,
  ROUTE_ORDER,
  STATUS_ORDER,
  formatCompactCurrency,
  formatLossType,
  formatPercent,
  formatRoute,
  formatStatus
} from "@/lib/claims";

type ChartDatum = {
  label: string;
  value: number;
  color: string;
};

const STATUS_COLORS: Record<string, string> = {
  open: "#2B5A9E",
  triaged: "#C98311",
  assessed: "#6B7280",
  settled: "#1F8A5B",
  denied: "#B94C3D"
};

const ROUTE_COLORS: Record<string, string> = {
  stp: "#C5A15A",
  desk: "#2B5A9E",
  field: "#1F8A5B",
  siu: "#7C3AED"
};

const LOSS_COLORS = ["#10223E", "#2B5A9E", "#C5A15A", "#1F8A5B", "#B94C3D", "#7C3AED"];

function Panel({
  title,
  subtitle,
  children,
  className = ""
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={["rounded-[28px] border border-white/70 bg-white/80 p-6 shadow-[0_20px_60px_rgba(16,34,62,0.08)] backdrop-blur", className].join(" ")}>
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-accent">Operational insight</p>
          <h2 className="mt-2 text-2xl font-semibold text-navy">{title}</h2>
          {subtitle ? <p className="mt-1 text-sm text-slate-500">{subtitle}</p> : null}
        </div>
      </div>
      {children}
    </section>
  );
}

function KpiCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-[24px] border border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(245,248,252,0.92))] p-5 shadow-[0_14px_40px_rgba(16,34,62,0.08)]">
      <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-accent">{label}</p>
      <p className="mt-4 text-4xl font-semibold text-navy">{value}</p>
      <p className="mt-3 text-sm text-slate-500">{detail}</p>
    </div>
  );
}

function BarChart({ items }: { items: ChartDatum[] }) {
  const max = Math.max(...items.map((item) => item.value), 1);
  const chartHeight = 168;
  const barWidth = 44;
  const gap = 24;
  const leftPad = 16;
  const chartWidth = leftPad * 2 + items.length * (barWidth + gap);

  return (
    <div className="space-y-4">
      <svg viewBox={`0 0 ${chartWidth} 236`} className="h-64 w-full">
        {[0, 0.25, 0.5, 0.75, 1].map((step) => {
          const y = 20 + chartHeight - chartHeight * step;
          return (
            <g key={step}>
              <line x1="12" y1={y} x2={chartWidth} y2={y} stroke="rgba(148, 163, 184, 0.2)" strokeDasharray="4 6" />
              <text x="0" y={y + 4} fontSize="10" fill="#64748B">
                {Math.round(max * step)}
              </text>
            </g>
          );
        })}
        {items.map((item, index) => {
          const height = max === 0 ? 0 : (item.value / max) * chartHeight;
          const x = leftPad + index * (barWidth + gap);
          const y = 20 + chartHeight - height;

          return (
            <g key={item.label}>
              <text x={x + barWidth / 2} y={y - 8} textAnchor="middle" fontSize="12" fill="#10223E" fontWeight="600">
                {item.value}
              </text>
              <rect x={x} y={y} width={barWidth} height={height} rx="14" fill={item.color} />
              <text x={x + barWidth / 2} y="218" textAnchor="middle" fontSize="11" fill="#475569">
                {item.label}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="grid gap-2 text-sm text-slate-500 sm:grid-cols-2 xl:grid-cols-3">
        {items.map((item) => (
          <div key={item.label} className="flex items-center justify-between rounded-2xl bg-slate-50/80 px-3 py-2">
            <span className="flex items-center gap-2 text-slate-600">
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
              {item.label}
            </span>
            <span className="font-semibold text-navy">{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function DonutChart({ items, total }: { items: ChartDatum[]; total: number }) {
  const gradient = (() => {
    if (total === 0) return "conic-gradient(#E2E8F0 0deg 360deg)";

    let current = 0;
    const segments = items.map((item) => {
      const degrees = (item.value / total) * 360;
      const start = current;
      const end = current + degrees;
      current = end;
      return `${item.color} ${start}deg ${end}deg`;
    });

    return `conic-gradient(${segments.join(", ")})`;
  })();

  return (
    <div className="grid gap-6 lg:grid-cols-[220px_minmax(0,1fr)] lg:items-center">
      <div className="mx-auto flex h-56 w-56 items-center justify-center rounded-full border border-white/80 bg-white/90 shadow-inner shadow-slate-900/5">
        <div className="relative flex h-44 w-44 items-center justify-center rounded-full" style={{ background: gradient }}>
          <div className="flex h-24 w-24 flex-col items-center justify-center rounded-full bg-white shadow-[inset_0_0_0_1px_rgba(148,163,184,0.12)]">
            <span className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400">Routed</span>
            <span className="mt-1 text-3xl font-semibold text-navy">{total}</span>
          </div>
        </div>
      </div>
      <div className="space-y-3">
        {items.map((item) => {
          const percentage = total === 0 ? 0 : item.value / total;
          return (
            <div key={item.label} className="rounded-[22px] border border-slate-200/70 bg-slate-50/80 px-4 py-3">
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <span className="h-3 w-3 rounded-full" style={{ backgroundColor: item.color }} />
                  <span className="font-medium text-slate-700">{item.label}</span>
                </div>
                <div className="text-right">
                  <p className="font-semibold text-navy">{item.value}</p>
                  <p className="text-xs text-slate-500">{formatPercent(percentage)}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const q = useQuery({
    queryKey: ["dashboard", "queue"],
    queryFn: () => api<ClaimRow[]>("/api/queue?limit=200"),
    staleTime: 30_000
  });

  const stats = useMemo(() => {
    const claims = q.data ?? [];
    const totalClaims = claims.length;
    const openClaims = claims.filter((claim) => !["settled", "denied"].includes(claim.Status)).length;
    const settledAmount = claims.reduce((sum, claim) => sum + (claim.SettledAmount ?? 0), 0);
    const fraudScores = claims.filter((claim) => claim.top_fraud_score != null).map((claim) => claim.top_fraud_score ?? 0);
    const avgFraudScore = fraudScores.length === 0 ? null : fraudScores.reduce((sum, score) => sum + score, 0) / fraudScores.length;
    const statusData = STATUS_ORDER.map((status) => ({
      label: formatStatus(status),
      value: claims.filter((claim) => claim.Status === status).length,
      color: STATUS_COLORS[status]
    }));
    const lossTypeMap = new Map<string, number>();

    claims.forEach((claim) => {
      const key = claim.LossType || "unclassified";
      lossTypeMap.set(key, (lossTypeMap.get(key) ?? 0) + 1);
    });

    const lossTypeData = Array.from(lossTypeMap.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
      .map(([lossType, value], index) => ({
        label: formatLossType(lossType),
        value,
        color: LOSS_COLORS[index % LOSS_COLORS.length]
      }));

    const routeData = ROUTE_ORDER.map((route) => ({
      label: formatRoute(route),
      value: claims.filter((claim) => claim.route === route).length,
      color: ROUTE_COLORS[route]
    }));
    const routedClaims = routeData.reduce((sum, item) => sum + item.value, 0);
    const unassignedRoutes = claims.filter((claim) => !claim.route).length;

    return {
      totalClaims,
      openClaims,
      settledAmount,
      avgFraudScore,
      statusData,
      lossTypeData,
      routeData,
      routedClaims,
      unassignedRoutes
    };
  }, [q.data]);

  if (q.isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="h-36 animate-pulse rounded-[24px] border border-white/80 bg-white/70" />
          ))}
        </div>
        <div className="grid gap-6 xl:grid-cols-2">
          <div className="h-96 animate-pulse rounded-[28px] border border-white/80 bg-white/70" />
          <div className="h-96 animate-pulse rounded-[28px] border border-white/80 bg-white/70" />
        </div>
      </div>
    );
  }

  if (q.isError) {
    return (
      <Panel title="Queue data unavailable" subtitle="The dashboard could not load claim telemetry from /api/queue.">
        <p className="text-sm text-red-700">{String(q.error)}</p>
      </Panel>
    );
  }

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-[32px] border border-white/70 bg-[linear-gradient(135deg,rgba(16,34,62,0.98),rgba(28,53,96,0.92)_58%,rgba(197,161,90,0.88))] px-6 py-8 text-white shadow-[0_24px_80px_rgba(9,23,44,0.24)] lg:px-8">
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-accent-soft">Claims processing command center</p>
            <h1 className="mt-3 max-w-3xl text-4xl font-semibold tracking-tight text-white lg:text-5xl">
              Premium operational oversight for triage, assessment, and settlement flow.
            </h1>
            <p className="mt-4 max-w-2xl text-base text-slate-200">
              The dashboard samples the latest 200 claims from the live queue API to surface workload mix, routing posture, and settlement progress in one executive-ready view.
            </p>
          </div>
          <div className="rounded-[24px] border border-white/15 bg-white/10 p-5 backdrop-blur">
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-300">Queue health</p>
            <p className="mt-3 text-3xl font-semibold">{stats.totalClaims} claims</p>
            <p className="mt-2 text-sm text-slate-200">Refreshed {new Date(q.dataUpdatedAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</p>
            <div className="mt-4 flex flex-wrap gap-3">
              <Link href="/claims" className="rounded-full bg-white px-4 py-2 text-sm font-medium text-navy shadow-sm hover:bg-slate-100">
                Open claims queue
              </Link>
              <Link href="/audit" className="rounded-full border border-white/20 px-4 py-2 text-sm font-medium text-white hover:bg-white/10">
                Review audit log
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Total claims" value={String(stats.totalClaims)} detail="Live queue sample volume feeding this dashboard." />
        <KpiCard label="Open claims" value={String(stats.openClaims)} detail="Claims still in-flight across triage, assessment, or manual routing." />
        <KpiCard label="Settled amount" value={formatCompactCurrency(stats.settledAmount)} detail="Aggregate settled exposure represented in the current sample." />
        <KpiCard label="Avg fraud score" value={formatPercent(stats.avgFraudScore)} detail="Mean normalized fraud signal across claims with recorded scores." />
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <Panel title="Claims by status" subtitle="Pipeline distribution across the core operating states.">
          <BarChart items={stats.statusData} />
        </Panel>
        <Panel title="Claims by loss type" subtitle="Top loss categories in the latest queue snapshot.">
          <BarChart items={stats.lossTypeData.length > 0 ? stats.lossTypeData : [{ label: "No data", value: 0, color: "#CBD5E1" }]} />
        </Panel>
      </section>

      <Panel title="Route distribution" subtitle="Desk assignment mix across straight-through, desk, field, and SIU handling.">
        <DonutChart items={stats.routeData} total={stats.routedClaims} />
        {stats.unassignedRoutes > 0 ? (
          <p className="mt-5 text-sm text-slate-500">
            {stats.unassignedRoutes} claims in the current sample do not yet have a route assignment.
          </p>
        ) : null}
      </Panel>
    </div>
  );
}
