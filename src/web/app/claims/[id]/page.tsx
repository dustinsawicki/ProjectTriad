"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";

type Doc = { document_id: string; doc_type: string; title: string | null; raw_text: string; extracted: Record<string, unknown> | null };
type Fraud = { signal_id: string; signal_type: string; score: number; rationale: Record<string, unknown> };
type Decision = { decision_id: string; agent_name: string; decision_type: string; payload: Record<string, unknown>; status: string; created_utc: string };
type Audit = { event_id: string; actor: string; actor_name: string; action: string; outcome: string; rationale: Record<string, unknown> | null; created_utc: string };
type Claim = {
  claim_id: string; claim_number: string; loss_type: string; status: string;
  reported_amount: number | null; reserve_amount: number | null; settled_amount: number | null;
  assigned_adjuster: string | null; created_utc: string;
};
type Policy = { policy_id: string; policy_number: string; product_line: string; coverage: Record<string, number | null>; status: string };
type Bundle = { claim: Claim; policy: Policy; documents: Doc[]; fraud_signals: Fraud[]; decisions: Decision[]; audit: Audit[] };

export default function ClaimWorkspace({ params }: { params: { id: string } }) {
  const qc = useQueryClient();
  const [settle, setSettle] = useState<string>("");

  const q = useQuery({
    queryKey: ["claim", params.id],
    queryFn: () => api<Bundle>(`/api/claims/${params.id}`),
    refetchInterval: 5000
  });

  const approve = useMutation({
    mutationFn: (amount: number) =>
      api(`/api/claims/${params.id}/approve`, {
        method: "POST",
        body: JSON.stringify({ settlement_amount: amount })
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["claim", params.id] })
  });

  if (q.isLoading) return <p>Loading …</p>;
  if (q.isError)   return <p className="text-red-700">{String(q.error)}</p>;
  if (!q.data)     return null;

  const { claim, policy, documents, fraud_signals, decisions, audit } = q.data;
  const proposedSettlement = decisions.find((d) => d.decision_type === "settlement" && d.status === "proposed");
  const topFraud = fraud_signals.reduce((max, s) => (s.score > max ? s.score : max), 0);
  const recommended = proposedSettlement ? (proposedSettlement.payload.settlement_amount as number) : undefined;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* Header card */}
      <div className="lg:col-span-3 bg-white rounded shadow p-4 flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-semibold text-navy">{claim.claim_number}</h1>
          <p className="text-slate-500 text-sm">
            {claim.loss_type} · policy {policy.policy_number} ({policy.product_line}) · adjuster {claim.assigned_adjuster ?? "—"}
          </p>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className={`px-3 py-1 rounded ${
            claim.status === "settled" ? "bg-emerald-100 text-emerald-700"
            : claim.status === "denied" ? "bg-red-100 text-red-700"
            : "bg-slate-100 text-slate-700"
          }`}>{claim.status}</span>
          <span>Fraud: <strong className={topFraud >= 0.7 ? "text-accent" : ""}>{topFraud.toFixed(2)}</strong></span>
          <span>Reported: <strong>${(claim.reported_amount ?? 0).toLocaleString()}</strong></span>
          <span>Settled: <strong>${(claim.settled_amount ?? 0).toLocaleString()}</strong></span>
        </div>
      </div>

      {/* Documents */}
      <section className="bg-white rounded shadow p-4 lg:col-span-2">
        <h2 className="font-semibold text-navy mb-2">Documents ({documents.length})</h2>
        <div className="space-y-3 max-h-96 overflow-auto pr-2">
          {documents.map((d) => (
            <details key={d.document_id} className="border rounded p-2">
              <summary className="cursor-pointer text-sm font-medium">
                {d.doc_type} {d.title ? `· ${d.title}` : ""}
              </summary>
              <pre className="mt-2 text-xs whitespace-pre-wrap text-slate-700">{d.raw_text}</pre>
              {d.extracted && (
                <pre className="mt-2 text-xs bg-slate-50 p-2 rounded">{JSON.stringify(d.extracted, null, 2)}</pre>
              )}
            </details>
          ))}
        </div>
      </section>

      {/* Fraud + agent decisions */}
      <section className="bg-white rounded shadow p-4 space-y-4">
        <div>
          <h2 className="font-semibold text-navy mb-2">Fraud signals</h2>
          <ul className="space-y-1 text-sm">
            {fraud_signals.length === 0 && <li className="text-slate-400">None recorded</li>}
            {fraud_signals.map((f) => (
              <li key={f.signal_id} className="flex justify-between">
                <span>{f.signal_type}</span>
                <span className={f.score >= 0.7 ? "text-accent font-semibold" : ""}>{f.score.toFixed(2)}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h2 className="font-semibold text-navy mb-2">Agent decisions</h2>
          <ul className="space-y-2 text-sm">
            {decisions.map((d) => (
              <li key={d.decision_id} className="border rounded p-2">
                <div className="flex justify-between">
                  <span className="font-medium">{d.agent_name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    d.status === "approved" ? "bg-emerald-100 text-emerald-700"
                    : d.status === "blocked" ? "bg-red-100 text-red-700"
                    : "bg-slate-100 text-slate-700"
                  }`}>{d.status}</span>
                </div>
                <pre className="text-xs mt-1 whitespace-pre-wrap text-slate-600">{JSON.stringify(d.payload, null, 2)}</pre>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Approve panel */}
      <section className="bg-white rounded shadow p-4 lg:col-span-2">
        <h2 className="font-semibold text-navy mb-2">Approve &amp; pay</h2>
        <p className="text-sm text-slate-500 mb-3">
          Recommended: <strong>${(recommended ?? 0).toLocaleString()}</strong>
        </p>
        <div className="flex items-center gap-2">
          <input
            className="border rounded px-2 py-1 w-40 tabular-nums"
            type="number" step="0.01" min="0"
            placeholder={recommended != null ? String(recommended) : "Amount"}
            value={settle}
            onChange={(e) => setSettle(e.target.value)}
          />
          <button
            className="bg-navy text-white px-4 py-1.5 rounded hover:bg-navy/90 disabled:opacity-50"
            disabled={claim.status === "settled" || approve.isPending}
            onClick={() => approve.mutate(Number(settle || recommended || 0))}
          >
            {approve.isPending ? "Submitting …" : "Approve & pay"}
          </button>
        </div>
      </section>

      {/* Audit */}
      <section className="bg-white rounded shadow p-4">
        <h2 className="font-semibold text-navy mb-2">Audit trail</h2>
        <ul className="space-y-1 text-xs">
          {audit.slice().reverse().map((a) => (
            <li key={a.event_id} className="flex justify-between gap-2 border-b pb-1">
              <span>
                <span className="font-mono text-slate-400">{new Date(a.created_utc).toLocaleString()}</span>{" "}
                <span className="font-medium">{a.actor_name}</span> · {a.action}
              </span>
              <span className={a.outcome === "block" ? "text-red-600" : "text-emerald-700"}>{a.outcome}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
