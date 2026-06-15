"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";

type Doc = { DocumentId: string; DocType: string; Title: string | null; RawText: string; ExtractedJson: Record<string, unknown> | null };
type Fraud = { SignalId: string; SignalType: string; Score: number; RationaleJson: Record<string, unknown> };
type Decision = { DecisionId: string; AgentName: string; DecisionType: string; Payload: Record<string, unknown>; Status: string; CreatedUtc: string };
type AuditEntry = { EventId: string; Actor: string; ActorName: string; Action: string; Outcome: string; RationaleJson: Record<string, unknown> | null; CreatedUtc: string };
type Claim = {
  ClaimId: string; ClaimNumber: string; LossType: string; Status: string;
  ReportedAmount: number | null; ReserveAmount: number | null; SettledAmount: number | null;
  AssignedAdjuster: string | null; CreatedUtc: string;
};
type Policy = { PolicyId: string; PolicyNumber: string; ProductLine: string; CoverageJson: Record<string, number | null>; Status: string };
type Bundle = { claim: Claim; policy: Policy; documents: Doc[]; fraud_signals: Fraud[]; decisions: Decision[]; audit: AuditEntry[] };

export default function ClaimWorkspace({ params }: { params: { id: string } }) {
  const { id } = params;
  const qc = useQueryClient();
  const [settle, setSettle] = useState<string>("");

  const q = useQuery({
    queryKey: ["claim", id],
    queryFn: () => api<Bundle>(`/api/claims/${id}`),
    refetchInterval: 5000
  });

  const approve = useMutation({
    mutationFn: (amount: number) =>
      api(`/api/claims/${id}/approve`, {
        method: "POST",
        body: JSON.stringify({ settlement_amount: amount })
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["claim", id] })
  });

  if (q.isLoading) return <p>Loading...</p>;
  if (q.isError)   return <p className="text-red-700">{String(q.error)}</p>;
  if (!q.data)     return null;

  const { claim, policy, documents, fraud_signals, decisions, audit } = q.data;
  const proposedSettlement = decisions.find((d) => d.DecisionType === "settlement" && d.Status === "proposed");
  const topFraud = fraud_signals.reduce((max, s) => (s.Score > max ? s.Score : max), 0);
  const recommended = proposedSettlement ? (proposedSettlement.Payload.settlement_amount as number) : undefined;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* Header card */}
      <div className="lg:col-span-3 bg-white rounded-2xl border border-white/70 shadow-[0_20px_60px_rgba(16,34,62,0.08)] p-5 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-navy">{claim.ClaimNumber}</h1>
          <p className="text-slate-500 text-sm">
            {claim.LossType} - policy {policy.PolicyNumber} ({policy.ProductLine}) - adjuster {claim.AssignedAdjuster ?? "--"}
          </p>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className={`px-3 py-1 rounded-full font-medium ${
            claim.Status === "settled" ? "bg-emerald-100 text-emerald-700"
            : claim.Status === "denied" ? "bg-red-100 text-red-700"
            : "bg-slate-100 text-slate-700"
          }`}>{claim.Status}</span>
          <span>Fraud: <strong className={topFraud >= 0.7 ? "text-accent" : ""}>{topFraud.toFixed(2)}</strong></span>
          <span>Reported: <strong>${(claim.ReportedAmount ?? 0).toLocaleString()}</strong></span>
          <span>Settled: <strong>${(claim.SettledAmount ?? 0).toLocaleString()}</strong></span>
        </div>
      </div>

      {/* Documents */}
      <section className="bg-white rounded-2xl border border-white/70 shadow-[0_20px_60px_rgba(16,34,62,0.08)] p-5 lg:col-span-2">
        <h2 className="font-semibold text-navy mb-3">Documents ({documents.length})</h2>
        <div className="space-y-3 max-h-96 overflow-auto pr-2">
          {documents.map((d) => (
            <details key={d.DocumentId} className="border border-slate-200 rounded-xl p-3">
              <summary className="cursor-pointer text-sm font-medium">
                {d.DocType} {d.Title ? `- ${d.Title}` : ""}
              </summary>
              <pre className="mt-2 text-xs whitespace-pre-wrap text-slate-700">{d.RawText}</pre>
              {d.ExtractedJson && (
                <pre className="mt-2 text-xs bg-slate-50 p-2 rounded">{JSON.stringify(d.ExtractedJson, null, 2)}</pre>
              )}
            </details>
          ))}
        </div>
      </section>

      {/* Fraud + agent decisions */}
      <section className="bg-white rounded-2xl border border-white/70 shadow-[0_20px_60px_rgba(16,34,62,0.08)] p-5 space-y-4">
        <div>
          <h2 className="font-semibold text-navy mb-2">Fraud signals</h2>
          <ul className="space-y-1 text-sm">
            {fraud_signals.length === 0 && <li className="text-slate-400">None recorded</li>}
            {fraud_signals.map((f) => (
              <li key={f.SignalId} className="flex justify-between">
                <span>{f.SignalType}</span>
                <span className={f.Score >= 0.7 ? "text-accent font-semibold" : ""}>{f.Score.toFixed(2)}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h2 className="font-semibold text-navy mb-2">Agent decisions</h2>
          <ul className="space-y-2 text-sm">
            {decisions.length === 0 && <li className="text-slate-400">No decisions yet</li>}
            {decisions.map((d) => (
              <li key={d.DecisionId} className="border border-slate-200 rounded-xl p-3">
                <div className="flex justify-between">
                  <span className="font-medium">{d.AgentName}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    d.Status === "approved" ? "bg-emerald-100 text-emerald-700"
                    : d.Status === "blocked" ? "bg-red-100 text-red-700"
                    : "bg-slate-100 text-slate-700"
                  }`}>{d.Status}</span>
                </div>
                <pre className="text-xs mt-1 whitespace-pre-wrap text-slate-600">{JSON.stringify(d.Payload, null, 2)}</pre>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Approve panel */}
      <section className="bg-white rounded-2xl border border-white/70 shadow-[0_20px_60px_rgba(16,34,62,0.08)] p-5 lg:col-span-2">
        <h2 className="font-semibold text-navy mb-2">Approve &amp; pay</h2>
        <p className="text-sm text-slate-500 mb-3">
          Recommended: <strong>${(recommended ?? 0).toLocaleString()}</strong>
        </p>
        <div className="flex items-center gap-2">
          <input
            className="border rounded-lg px-3 py-2 w-40 tabular-nums"
            type="number" step="0.01" min="0"
            placeholder={recommended != null ? String(recommended) : "Amount"}
            value={settle}
            onChange={(e) => setSettle(e.target.value)}
          />
          <button
            className="bg-navy text-white px-4 py-2 rounded-lg hover:bg-navy/90 disabled:opacity-50 font-medium"
            disabled={claim.Status === "settled" || approve.isPending}
            onClick={() => approve.mutate(Number(settle || recommended || 0))}
          >
            {approve.isPending ? "Submitting..." : "Approve & pay"}
          </button>
        </div>
      </section>

      {/* Audit */}
      <section className="bg-white rounded-2xl border border-white/70 shadow-[0_20px_60px_rgba(16,34,62,0.08)] p-5">
        <h2 className="font-semibold text-navy mb-2">Audit trail</h2>
        <ul className="space-y-1 text-xs">
          {audit.slice().reverse().map((a) => (
            <li key={a.EventId} className="flex justify-between gap-2 border-b pb-1">
              <span>
                <span className="font-mono text-slate-400">{new Date(a.CreatedUtc).toLocaleString()}</span>{" "}
                <span className="font-medium">{a.ActorName}</span> - {a.Action}
              </span>
              <span className={a.Outcome === "block" ? "text-red-600" : "text-emerald-700"}>{a.Outcome}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
