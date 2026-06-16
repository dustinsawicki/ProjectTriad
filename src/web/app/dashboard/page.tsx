"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Legend, AreaChart, Area
} from "recharts";

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

const COLORS = ["#0ea5e9", "#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];
const STATUS_COLORS: Record<string, string> = {
  open: "#0ea5e9",
  triaged: "#6366f1",
  assessed: "#f59e0b",
  settled: "#10b981",
  denied: "#ef4444",
};

function fmt(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

function KpiCard({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: string }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-5 flex flex-col gap-1 hover:shadow-md transition-shadow">
      <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">{label}</span>
      <span className={`text-2xl font-bold ${accent ?? "text-slate-800"}`}>{value}</span>
      {sub && <span className="text-xs text-slate-400">{sub}</span>}
    </div>
  );
}

export default function DashboardPage() {
  const q = useQuery({ queryKey: ["queue-all"], queryFn: () => api<ClaimRow[]>("/api/queue") });
  const claims = q.data ?? [];

  // KPI metrics
  const total = claims.length;
  const openCount = claims.filter(c => c.status === "open").length;
  const settledCount = claims.filter(c => c.status === "settled").length;
  const deniedCount = claims.filter(c => c.status === "denied").length;
  const siuCount = claims.filter(c => c.route === "siu").length;
  const totalReserve = claims.reduce((s, c) => s + (c.reserve_amount ?? 0), 0);
  const totalSettled = claims.reduce((s, c) => s + (c.settled_amount ?? 0), 0);
  const avgFraud = claims.filter(c => c.top_fraud_score != null).length > 0
    ? claims.reduce((s, c) => s + (c.top_fraud_score ?? 0), 0) / claims.filter(c => c.top_fraud_score != null).length
    : 0;

  // Status distribution
  const statusMap: Record<string, number> = {};
  claims.forEach(c => { statusMap[c.status] = (statusMap[c.status] ?? 0) + 1; });
  const statusData = Object.entries(statusMap).map(([name, value]) => ({ name, value }));

  // Loss type distribution
  const lossMap: Record<string, number> = {};
  claims.forEach(c => { lossMap[c.loss_type] = (lossMap[c.loss_type] ?? 0) + 1; });
  const lossData = Object.entries(lossMap)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8);

  // Fraud score distribution (histogram buckets)
  const fraudBuckets = Array.from({ length: 10 }, (_, i) => ({
    range: `${(i * 0.1).toFixed(1)}-${((i + 1) * 0.1).toFixed(1)}`,
    count: 0
  }));
  claims.forEach(c => {
    if (c.top_fraud_score != null) {
      const idx = Math.min(Math.floor(c.top_fraud_score * 10), 9);
      fraudBuckets[idx].count++;
    }
  });

  // Claims over time (by month)
  const timeMap: Record<string, number> = {};
  claims.forEach(c => {
    const d = new Date(c.created_utc);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    timeMap[key] = (timeMap[key] ?? 0) + 1;
  });
  const timeData = Object.entries(timeMap)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([month, count]) => ({ month, count }));

  // Route breakdown
  const routeMap: Record<string, number> = {};
  claims.forEach(c => {
    const r = c.route ?? "unassigned";
    routeMap[r] = (routeMap[r] ?? 0) + 1;
  });
  const routeData = Object.entries(routeMap).map(([name, value]) => ({ name: name.toUpperCase(), value }));

  if (q.isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse flex flex-col items-center gap-3">
          <div className="w-10 h-10 rounded-full border-4 border-sky-200 border-t-sky-500 animate-spin" />
          <span className="text-slate-400 text-sm">Loading dashboard…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Dashboard</h1>
        <p className="text-sm text-slate-400 mt-1">Real-time overview of claims processing pipeline</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
        <KpiCard label="Total Claims" value={total.toLocaleString()} />
        <KpiCard label="Open" value={openCount.toLocaleString()} accent="text-sky-600" />
        <KpiCard label="Settled" value={settledCount.toLocaleString()} accent="text-emerald-600" />
        <KpiCard label="Denied" value={deniedCount.toLocaleString()} accent="text-red-500" />
        <KpiCard label="SIU Referrals" value={siuCount.toLocaleString()} accent="text-purple-600" />
        <KpiCard label="Total Reserve" value={fmt(totalReserve)} />
        <KpiCard label="Avg Fraud Score" value={avgFraud.toFixed(2)} accent={avgFraud > 0.5 ? "text-red-500" : "text-emerald-600"} />
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Status Distribution */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-5">
          <h2 className="text-sm font-semibold text-slate-600 mb-4">Claims by Status</h2>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie data={statusData} cx="50%" cy="50%" innerRadius={60} outerRadius={100}
                paddingAngle={3} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                {statusData.map((entry, i) => (
                  <Cell key={entry.name} fill={STATUS_COLORS[entry.name] ?? COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Loss Type Distribution */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-5">
          <h2 className="text-sm font-semibold text-slate-600 mb-4">Top Loss Types</h2>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={lossData} layout="vertical" margin={{ left: 80 }}>
              <XAxis type="number" />
              <YAxis type="category" dataKey="name" width={75} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                {lossData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Charts row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Fraud Score Distribution */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-5">
          <h2 className="text-sm font-semibold text-slate-600 mb-4">Fraud Score Distribution</h2>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={fraudBuckets}>
              <XAxis dataKey="range" tick={{ fontSize: 10 }} />
              <YAxis />
              <Tooltip />
              <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Claims Over Time */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-5">
          <h2 className="text-sm font-semibold text-slate-600 mb-4">Claims Over Time</h2>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={timeData}>
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis />
              <Tooltip />
              <Area type="monotone" dataKey="count" stroke="#0ea5e9" fill="#0ea5e9" fillOpacity={0.15} strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Route Breakdown */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-5">
          <h2 className="text-sm font-semibold text-slate-600 mb-4">Routing Breakdown</h2>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={routeData} cx="50%" cy="50%" outerRadius={80}
                dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                {routeData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Financial summary */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-5">
          <h2 className="text-sm font-semibold text-slate-600 mb-3">Financial Summary</h2>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-slate-500">Total Reported</span>
              <span className="font-semibold text-slate-800">{fmt(claims.reduce((s, c) => s + (c.reported_amount ?? 0), 0))}</span>
            </div>
            <div className="h-px bg-slate-100" />
            <div className="flex justify-between items-center">
              <span className="text-slate-500">Total Reserve</span>
              <span className="font-semibold text-amber-600">{fmt(totalReserve)}</span>
            </div>
            <div className="h-px bg-slate-100" />
            <div className="flex justify-between items-center">
              <span className="text-slate-500">Total Settled</span>
              <span className="font-semibold text-emerald-600">{fmt(totalSettled)}</span>
            </div>
            <div className="h-px bg-slate-100" />
            <div className="flex justify-between items-center">
              <span className="text-slate-500">Savings (Reserve − Settled)</span>
              <span className="font-bold text-sky-600">{fmt(totalReserve - totalSettled)}</span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-5">
          <h2 className="text-sm font-semibold text-slate-600 mb-3">Pipeline Health</h2>
          <div className="space-y-4">
            {[
              { label: "Open → Triaged", pct: total > 0 ? ((statusMap["triaged"] ?? 0) / total * 100) : 0, color: "bg-indigo-500" },
              { label: "Triaged → Assessed", pct: total > 0 ? ((statusMap["assessed"] ?? 0) / total * 100) : 0, color: "bg-amber-500" },
              { label: "Assessed → Settled", pct: total > 0 ? ((statusMap["settled"] ?? 0) / total * 100) : 0, color: "bg-emerald-500" },
              { label: "Denial Rate", pct: total > 0 ? ((statusMap["denied"] ?? 0) / total * 100) : 0, color: "bg-red-500" },
            ].map(({ label, pct, color }) => (
              <div key={label}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-500">{label}</span>
                  <span className="font-medium text-slate-700">{pct.toFixed(1)}%</span>
                </div>
                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
