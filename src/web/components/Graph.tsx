"use client";

import { useEffect, useRef } from "react";

interface Node {
  id: string;
  label: string;
  is_focus?: boolean;
}

interface Edge {
  id: string;
  from: string;
  to: string;
  type: string;
  weight: number;
  label: string;
}

interface GraphProps {
  nodes: Node[];
  edges: Edge[];
}

export default function Graph({ nodes, edges }: GraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || nodes.length === 0) return;

    // Dynamic import of vis-network (client-side only)
    import("vis-network/standalone").then(({ Network }) => {
      const visNodes = nodes.map((n) => ({
        id: n.id,
        label: n.label,
        color: n.is_focus
          ? { background: "#ef4444", border: "#991b1b" }
          : { background: "#3b82f6", border: "#1d4ed8" },
        font: { color: "#ffffff" },
        shape: "dot",
        size: n.is_focus ? 20 : 12,
      }));

      const edgeColors: Record<string, string> = {
        shared_phone: "#f59e0b",
        shared_address: "#10b981",
        shared_vin: "#8b5cf6",
      };

      const visEdges = edges.map((e) => ({
        id: e.id,
        from: e.from,
        to: e.to,
        label: e.label,
        color: edgeColors[e.type] || "#6b7280",
        width: Math.max(1, e.weight * 3),
        font: { size: 10, color: "#9ca3af" },
      }));

      const data = { nodes: visNodes, edges: visEdges };
      const options = {
        physics: {
          solver: "forceAtlas2Based",
          forceAtlas2Based: { gravitationalConstant: -50 },
          stabilization: { iterations: 150 },
        },
        interaction: { hover: true, zoomView: true, dragView: true },
      };

      new Network(containerRef.current!, data, options);
    });
  }, [nodes, edges]);

  return (
    <div
      ref={containerRef}
      className="w-full h-[600px] border border-gray-700 rounded-lg bg-gray-900"
    />
  );
}
