import { useEffect, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type DashboardBid = {
  bid_id: string;
  tender_id: string;
  tender_title: string;
  bidder_id: string;
  bidder_name: string;
  enterprise_category: string | null;
  status: string;
  overall_score: number | null;
  risk_level: string | null;
};

export default function App() {
  const [bids, setBids] = useState<DashboardBid[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/dashboard/bids`)
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then(setBids)
      .catch((cause: Error) => setError(cause.message));
  }, []);

  return (
    <main className="mx-auto max-w-6xl p-8">
      <h1 className="text-2xl font-semibold">GeM Bid Compliance</h1>
      <p className="mt-1 text-sm text-slate-500">
        {error ? `Failed to load bids: ${error}` : `${bids.length} bids`}
      </p>

      <table className="mt-6 w-full text-left text-sm">
        <thead className="border-b text-slate-500">
          <tr>
            <th className="py-2">Bid</th>
            <th className="py-2">Bidder</th>
            <th className="py-2">Tender</th>
            <th className="py-2">Status</th>
            <th className="py-2">Score</th>
            <th className="py-2">Risk</th>
          </tr>
        </thead>
        <tbody>
          {bids.map((bid) => (
            <tr key={bid.bid_id} className="border-b">
              <td className="py-2 font-mono text-xs">{bid.bid_id}</td>
              <td className="py-2">{bid.bidder_name}</td>
              <td className="py-2">{bid.tender_title}</td>
              <td className="py-2">{bid.status}</td>
              <td className="py-2">{bid.overall_score ?? "—"}</td>
              <td className="py-2">{bid.risk_level ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
