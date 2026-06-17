"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";

interface ClaimEvent {
  event_id: string;
  event_type: string;
  claim_number: string;
  claim_id: string;
  agent?: string;
  correlation_id?: string;
  occurred_utc: string;
  detail?: Record<string, unknown>;
}

const EVENT_STYLES: Record<string, string> = {
  fnol_complete: "bg-sky-50 text-sky-700 ring-1 ring-sky-200",
  triage_complete: "bg-indigo-50 text-indigo-700 ring-1 ring-indigo-200",
  assessment_complete: "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
  guardrail_complete: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
  pipeline_complete: "bg-slate-700 text-white",
  policy_invalid: "bg-red-50 text-red-700 ring-1 ring-red-200",
};

function EventBadge({ type }: { type: string }) {
  const label = type.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
  return (
    <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${EVENT_STYLES[type] ?? "bg-slate-100 text-slate-600"}`}>
      {label}
    </span>
  );
}

export default function SupervisorPage() {
  const [events, setEvents] = useState<ClaimEvent[]>([]);
  const [loading, setLoading] = useState(true);

  const loadEvents = useCallback(() => {
    api<ClaimEvent[]>("/api/events/recent?limit=100")
      .then((data) => { setEvents(data); setLoading(false); })
      .catch(console.error);
  }, []);

  useEffect(() => {
    loadEvents();
    const interval = setInterval(loadEvents, 5000);
    return () => clearInterval(interval);
  }, [loadEvents]);

  // Stats
  const pipelineEvents = events.filter(e => e.event_type === "pipeline_complete");
  const guardrailBlocks = events.filter(e => e.event_type === "guardrail_complete" && (e.detail as Record<string, unknown>)?.outcome === "block");
  const uniqueClaims = new Set(events.map(e => e.claim_id)).size;
  const agents = new Set(events.filter(e => e.agent).map(e => e.agent));

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Supervisor Dashboard</h1>
          <p className="text-sm text-slate-400 mt-0.5">Real-time agent pipeline activity</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-4">
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Pipeline Runs</span>
          <p className="text-2xl font-bold text-slate-800 mt-1">{pipelineEvents.length}</p>
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-4">
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Unique Claims</span>
          <p className="text-2xl font-bold text-sky-600 mt-1">{uniqueClaims}</p>
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-4">
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Active Agents</span>
          <p className="text-2xl font-bold text-indigo-600 mt-1">{agents.size}</p>
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-4">
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Guardrail Blocks</span>
          <p className="text-2xl font-bold text-red-500 mt-1">{guardrailBlocks.length}</p>
        </div>
      </div>

      {/* Event Log */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-600">Live Event Stream</h2>
          <span className="flex items-center gap-1.5 text-xs text-emerald-500">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            Auto-refreshing
          </span>
        </div>
        <div className="overflow-auto max-h-[500px]">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider sticky top-0">
              <tr>
                <th className="px-4 py-3 text-left">Time</th>
                <th className="px-4 py-3 text-left">Claim</th>
                <th className="px-4 py-3 text-left">Event</th>
                <th className="px-4 py-3 text-left">Agent</th>
                <th className="px-4 py-3 text-left">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && (
                <tr><td colSpan={5} className="px-4 py-12 text-center text-slate-400">
                  <div className="flex items-center justify-center gap-2">
                    <div className="w-4 h-4 rounded-full border-2 border-sky-200 border-t-sky-500 animate-spin" />
                    Loading events…
                  </div>
                </td></tr>
              )}
              {!loading && events.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-12 text-center text-slate-400">
                  No events yet. Process a claim or click &quot;Seed Demo Events&quot;.
                </td></tr>
              )}
              {events.map((evt) => (
                <tr key={evt.event_id} className="hover:bg-sky-50/50 transition-colors">
                  <td className="px-4 py-3 font-mono text-xs text-slate-400 whitespace-nowrap">
                    {new Date(evt.occurred_utc).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 font-mono text-sm font-medium text-sky-600">{evt.claim_number}</td>
                  <td className="px-4 py-3"><EventBadge type={evt.event_type} /></td>
                  <td className="px-4 py-3 text-xs text-slate-500">{evt.agent ?? "—"}</td>
                  <td className="px-4 py-3 text-xs text-slate-400 max-w-xs truncate">
                    {evt.detail && Object.keys(evt.detail).length > 0
                      ? <code className="bg-slate-50 px-2 py-0.5 rounded">{JSON.stringify(evt.detail)}</code>
                      : <span className="text-slate-300">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
