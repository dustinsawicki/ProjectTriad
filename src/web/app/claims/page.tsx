"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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

type CreateClaimOut = {
  claim_id: string;
  claim_number: string;
  pipeline_correlation_id: string;
};

const STATUSES = ["", "open", "triaged", "assessed", "settled", "denied"];
const ROUTES   = ["", "stp", "desk", "field", "siu"];
const LOSS_TYPES = ["auto_collision", "auto_comp", "home_property", "liability"];

const statusStyle: Record<string, string> = {
  open:     "bg-sky-50 text-sky-700 ring-1 ring-sky-200",
  triaged:  "bg-indigo-50 text-indigo-700 ring-1 ring-indigo-200",
  assessed: "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
  settled:  "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
  denied:   "bg-red-50 text-red-700 ring-1 ring-red-200",
};

const SAMPLE_DOCS: Record<string, { doc_type: string; title: string; raw_text: string }[]> = {
  auto_collision: [
    { doc_type: "police_report", title: "Police Report – Rear-End Collision", raw_text: "On the reported date, the insured vehicle was rear-ended at a traffic signal. The other driver admitted fault. Damage to rear bumper, trunk, and tail lights. No injuries reported. Report filed by Officer Martinez, Badge #4421." },
    { doc_type: "estimate", title: "Body Shop Repair Estimate", raw_text: "Rear bumper replacement: $3,200. Trunk lid repair: $4,800. Tail light assembly: $1,500. Paint and labor: $3,000. Total estimate: $12,500." },
  ],
  auto_comp: [
    { doc_type: "police_report", title: "Police Report – Vehicle Theft", raw_text: "Insured reported vehicle stolen from a shopping center parking lot. Security camera footage shows an unidentified individual entering the vehicle at 2:15 AM. Vehicle recovered 3 days later with significant interior damage." },
    { doc_type: "estimate", title: "Damage Assessment", raw_text: "Interior restoration: $4,500. Ignition column repair: $1,800. Window replacement: $900. Detailing and cleanup: $600. Total: $7,800." },
  ],
  home_property: [
    { doc_type: "police_report", title: "Incident Report – Storm Damage", raw_text: "Severe thunderstorm with 70mph winds caused a large oak tree to fall onto the insured property, damaging the roof and front porch. Neighbor witnessed the event. No injuries." },
    { doc_type: "estimate", title: "Contractor Repair Estimate", raw_text: "Roof repair (12x20 section): $18,000. Porch reconstruction: $8,500. Tree removal and cleanup: $2,200. Temporary tarp and boarding: $800. Total: $29,500." },
  ],
  liability: [
    { doc_type: "medical", title: "Medical Report – Slip and Fall", raw_text: "Patient presented with a sprained ankle and minor contusions after slipping on the insured's property. X-rays negative for fractures. Recommended 2 weeks rest and physical therapy." },
    { doc_type: "estimate", title: "Medical Expense Summary", raw_text: "Emergency room visit: $2,800. X-rays: $450. Ankle brace: $120. Physical therapy (6 sessions): $1,200. Prescription medication: $85. Total: $4,655." },
  ],
};

function NewClaimModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: (r: CreateClaimOut) => void }) {
  const [policyNumber, setPolicyNumber] = useState("");
  const [lossType, setLossType] = useState("auto_collision");
  const [reportedAmount, setReportedAmount] = useState("12500");
  const [lossDate, setLossDate] = useState(new Date().toISOString().slice(0, 16));
  const [includeDocuments, setIncludeDocuments] = useState(true);

  const policiesQuery = useQuery({
    queryKey: ["policies"],
    queryFn: () => api<{ policy_number: string; product_line: string }[]>("/api/seed/policies"),
  });
  const policies = policiesQuery.data ?? [];

  // Set first policy as default once loaded
  if (policies.length > 0 && !policyNumber) {
    setPolicyNumber(policies[0].policy_number);
  }

  const mutation = useMutation({
    mutationFn: () => {
      const docs = includeDocuments ? (SAMPLE_DOCS[lossType] ?? []) : [];
      return api<CreateClaimOut>("/api/claims", {
        method: "POST",
        body: JSON.stringify({
          policy_number: policyNumber,
          loss_datetime: new Date(lossDate).toISOString(),
          loss_type: lossType,
          reported_amount: parseFloat(reportedAmount) || null,
          documents: docs,
        }),
      });
    },
    onSuccess: (data) => onSuccess(data),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="bg-gradient-to-r from-sky-500 to-indigo-500 px-6 py-4">
          <h2 className="text-lg font-bold text-white">Submit New Claim</h2>
          <p className="text-sky-100 text-sm">This will create a claim and trigger the agent pipeline</p>
        </div>
        <div className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Policy Number</span>
              <select className="border border-slate-200 rounded-lg px-3 py-2 bg-white shadow-sm focus:ring-2 focus:ring-sky-200 focus:border-sky-400 outline-none text-sm"
                value={policyNumber} onChange={(e) => setPolicyNumber(e.target.value)}>
                {policiesQuery.isLoading && <option>Loading…</option>}
                {policies.map((p) => (
                  <option key={p.policy_number} value={p.policy_number}>{p.policy_number} ({p.product_line})</option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Loss Type</span>
              <select className="border border-slate-200 rounded-lg px-3 py-2 bg-white shadow-sm focus:ring-2 focus:ring-sky-200 focus:border-sky-400 outline-none text-sm"
                value={lossType} onChange={(e) => setLossType(e.target.value)}>
                {LOSS_TYPES.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
              </select>
            </label>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Loss Date/Time</span>
              <input type="datetime-local" className="border border-slate-200 rounded-lg px-3 py-2 bg-white shadow-sm focus:ring-2 focus:ring-sky-200 focus:border-sky-400 outline-none text-sm"
                value={lossDate} onChange={(e) => setLossDate(e.target.value)} />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Reported Amount ($)</span>
              <input type="number" min="0" step="100" className="border border-slate-200 rounded-lg px-3 py-2 bg-white shadow-sm focus:ring-2 focus:ring-sky-200 focus:border-sky-400 outline-none text-sm"
                value={reportedAmount} onChange={(e) => setReportedAmount(e.target.value)} />
            </label>
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={includeDocuments} onChange={(e) => setIncludeDocuments(e.target.checked)}
              className="w-4 h-4 rounded border-slate-300 text-sky-500 focus:ring-sky-300" />
            <span className="text-sm text-slate-600">Include sample documents ({(SAMPLE_DOCS[lossType] ?? []).length} docs for {lossType.replace("_", " ")})</span>
          </label>
          {includeDocuments && (
            <div className="bg-slate-50 rounded-lg p-3 space-y-2 max-h-32 overflow-y-auto">
              {(SAMPLE_DOCS[lossType] ?? []).map((d, i) => (
                <div key={i} className="text-xs">
                  <span className="font-medium text-slate-600">{d.title}</span>
                  <span className="text-slate-400 ml-2">({d.doc_type})</span>
                  <p className="text-slate-400 mt-0.5 line-clamp-1">{d.raw_text}</p>
                </div>
              ))}
            </div>
          )}
          {mutation.isError && (
            <div className="bg-red-50 text-red-700 text-sm rounded-lg px-4 py-2 ring-1 ring-red-200">
              {String(mutation.error)}
            </div>
          )}
          {mutation.isSuccess && mutation.data && (
            <div className="bg-emerald-50 text-emerald-700 text-sm rounded-lg px-4 py-3 ring-1 ring-emerald-200">
              <p className="font-medium">✓ Claim {mutation.data.claim_number} created!</p>
              <p className="text-xs mt-1 text-emerald-600">Agent pipeline triggered • Correlation: {mutation.data.pipeline_correlation_id}</p>
              <Link href={`/claims/${mutation.data.claim_id}`} className="text-xs underline hover:text-emerald-800 mt-1 inline-block">
                View claim details →
              </Link>
            </div>
          )}
        </div>
        <div className="border-t border-slate-100 px-6 py-4 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-500 hover:text-slate-700 rounded-lg hover:bg-slate-50 transition-colors">
            {mutation.isSuccess ? "Close" : "Cancel"}
          </button>
          {!mutation.isSuccess && (
            <button onClick={() => mutation.mutate()} disabled={mutation.isPending}
              className="px-5 py-2 text-sm font-medium text-white bg-gradient-to-r from-sky-500 to-indigo-500 rounded-lg hover:from-sky-600 hover:to-indigo-600 shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2">
              {mutation.isPending ? (
                <><div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" /> Submitting…</>
              ) : (
                <><svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" /></svg> Submit Claim</>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ClaimsQueue() {
  const [status, setStatus] = useState("");
  const [route, setRoute]   = useState("");
  const [minFraud, setMinFraud] = useState("");
  const [showNewClaim, setShowNewClaim] = useState(false);
  const qc = useQueryClient();

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
      {showNewClaim && (
        <NewClaimModal
          onClose={() => setShowNewClaim(false)}
          onSuccess={() => { qc.invalidateQueries({ queryKey: ["queue"] }); }}
        />
      )}
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Claims Queue</h1>
          <p className="text-sm text-slate-400 mt-0.5">{q.data ? `${q.data.length} claims` : "Loading…"}</p>
        </div>
        <div className="flex gap-3 text-sm items-end">
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
          <button onClick={() => setShowNewClaim(true)}
            className="px-4 py-1.5 text-sm font-medium text-white bg-gradient-to-r from-sky-500 to-indigo-500 rounded-lg hover:from-sky-600 hover:to-indigo-600 shadow-md hover:shadow-lg transition-all flex items-center gap-1.5">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" /></svg>
            New Claim
          </button>
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
