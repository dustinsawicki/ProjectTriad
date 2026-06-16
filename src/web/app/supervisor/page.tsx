"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";

interface ClaimEvent {
  event_id: string;
  event_type: string;
  claim_number: string;
  occurred_utc: string;
}

export default function SupervisorPage() {
  const [events, setEvents] = useState<ClaimEvent[]>([]);
  const [replaying, setReplaying] = useState(false);

  const loadEvents = useCallback(() => {
    api<ClaimEvent[]>("/api/events/recent?limit=50")
      .then(setEvents)
      .catch(console.error);
  }, []);

  useEffect(() => {
    loadEvents();
    const interval = setInterval(loadEvents, 5000);
    return () => clearInterval(interval);
  }, [loadEvents]);

  const handleReplay = async () => {
    setReplaying(true);
    try {
      await api("/api/supervisor/replay-telematics", { method: "POST" });
    } catch (e) {
      console.error("Replay failed:", e);
    } finally {
      setTimeout(() => setReplaying(false), 3000);
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Supervisor Dashboard</h1>
        <button
          onClick={handleReplay}
          disabled={replaying}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 rounded text-white text-sm"
        >
          {replaying ? "Replaying..." : "Replay Telematics"}
        </button>
      </div>

      {/* App Insights Workbook Embed Placeholder */}
      <div className="mb-8 border border-gray-700 rounded-lg p-4 bg-gray-900">
        <h2 className="text-lg font-semibold mb-2">App Insights Workbook</h2>
        <p className="text-gray-400 text-sm mb-4">
          Claims/hour · Agent latency · Fraud rate · Guardrail blocks
        </p>
        <div className="w-full h-[400px] bg-gray-800 rounded flex items-center justify-center text-gray-500">
          {/* In production, this iframe embeds the App Insights workbook */}
          <p>Workbook embed renders here when deployed with PKCE auth configured</p>
        </div>
      </div>

      {/* Live Event Log */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Recent Claim Events</h2>
        <div className="overflow-auto max-h-[400px] border border-gray-700 rounded-lg">
          <table className="w-full text-sm">
            <thead className="bg-gray-800 sticky top-0">
              <tr>
                <th className="px-3 py-2 text-left">Time</th>
                <th className="px-3 py-2 text-left">Claim</th>
                <th className="px-3 py-2 text-left">Event</th>
              </tr>
            </thead>
            <tbody>
              {events.length === 0 && (
                <tr>
                  <td colSpan={3} className="px-3 py-4 text-center text-gray-500">
                    No events yet. Process a claim to see events appear.
                  </td>
                </tr>
              )}
              {events.map((evt) => (
                <tr key={evt.event_id} className="border-t border-gray-700 hover:bg-gray-800">
                  <td className="px-3 py-2 text-gray-400 font-mono text-xs">
                    {new Date(evt.occurred_utc).toLocaleTimeString()}
                  </td>
                  <td className="px-3 py-2">{evt.claim_number}</td>
                  <td className="px-3 py-2">
                    <span className="px-2 py-0.5 rounded text-xs bg-blue-900 text-blue-200">
                      {evt.event_type}
                    </span>
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
