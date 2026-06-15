"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Graph from "@/components/Graph";
import { api } from "@/lib/api";

interface GraphData {
  nodes: Array<{ id: string; label: string; is_focus?: boolean }>;
  edges: Array<{ id: string; from: string; to: string; type: string; weight: number; label: string }>;
}

function SiuGraphContent() {
  const searchParams = useSearchParams();
  const claimId = searchParams.get("claim") || "";
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!claimId) {
      setLoading(false);
      return;
    }

    setLoading(true);
    api<GraphData>(`/api/siu/graph?claim=${encodeURIComponent(claimId)}`)
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, [claimId]);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">SIU Link Graph</h1>
      <p className="text-gray-400 mb-4">
        Fraud ring visualization for claim:{" "}
        <code className="bg-gray-800 px-2 py-1 rounded">{claimId || "(none)"}</code>
      </p>

      {loading && <p className="text-gray-400">Loading graph...</p>}
      {error && <p className="text-red-400">Error: {error}</p>}
      {!loading && !claimId && (
        <p className="text-yellow-400">
          Provide a <code>?claim=CLM-200008</code> query parameter to view the link graph.
        </p>
      )}
      {data && data.nodes.length === 0 && (
        <p className="text-gray-400">No link-graph data found for this claim.</p>
      )}
      {data && data.nodes.length > 0 && <Graph nodes={data.nodes} edges={data.edges} />}

      <div className="mt-6 grid grid-cols-3 gap-4 text-sm">
        <div className="flex items-center gap-2">
          <span className="w-4 h-4 rounded-full bg-yellow-500"></span>
          shared_phone
        </div>
        <div className="flex items-center gap-2">
          <span className="w-4 h-4 rounded-full bg-green-500"></span>
          shared_address
        </div>
        <div className="flex items-center gap-2">
          <span className="w-4 h-4 rounded-full bg-purple-500"></span>
          shared_vin
        </div>
      </div>
    </div>
  );
}

export default function SiuGraphPage() {
  return (
    <Suspense fallback={<div className="p-6"><p className="text-gray-400">Loading...</p></div>}>
      <SiuGraphContent />
    </Suspense>
  );
}
