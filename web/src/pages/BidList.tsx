import { ArrowDown, ArrowUp, ArrowUpDown, ChevronRight, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { RiskBadge, StatusBadge } from "@/components/badges";
import { Card } from "@/components/ui/card";
import { api, toNumber, type BidStatus, type DashboardBid, type RiskLevel } from "@/lib/api";
import { formatScore, STATUS_LABELS } from "@/lib/format";
import { bidHref } from "@/lib/router";
import { cn } from "@/lib/utils";

const RISK_ORDER: (RiskLevel | "unverified")[] = ["Non-Compliant", "High", "Medium", "Low", "unverified"];

const RISK_TILE: Record<RiskLevel | "unverified", { label: string; className: string }> = {
  "Non-Compliant": { label: "Non-Compliant", className: "border-l-red-700" },
  High: { label: "High risk", className: "border-l-red-400" },
  Medium: { label: "Medium risk", className: "border-l-amber-400" },
  Low: { label: "Low risk", className: "border-l-emerald-500" },
  unverified: { label: "Not verified", className: "border-l-slate-300" },
};

type SortKey = "bid" | "score";

export default function BidList() {
  const [bids, setBids] = useState<DashboardBid[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tender, setTender] = useState("all");
  const [status, setStatus] = useState<BidStatus | "all">("all");
  const [risk, setRisk] = useState<RiskLevel | "unverified" | "all">("all");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({ key: "bid", dir: "asc" });

  useEffect(() => {
    api.listBids().then(setBids, (cause: Error) => setError(cause.message));
  }, []);

  const tenders = useMemo(() => {
    const seen = new Map<string, string>();
    bids?.forEach((bid) => seen.set(bid.tender_id, bid.tender_title));
    return [...seen].sort(([a], [b]) => a.localeCompare(b));
  }, [bids]);

  // Tiles count within the tender filter, so they stay meaningful while drilling into one tender.
  const inTender = useMemo(() => (bids ?? []).filter((bid) => tender === "all" || bid.tender_id === tender), [bids, tender]);

  const riskCounts = useMemo(() => {
    const counts = Object.fromEntries(RISK_ORDER.map((key) => [key, 0])) as Record<RiskLevel | "unverified", number>;
    inTender.forEach((bid) => counts[bid.risk_level ?? "unverified"]++);
    return counts;
  }, [inTender]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const rows = inTender.filter(
      (bid) =>
        (status === "all" || bid.status === status) &&
        (risk === "all" || (bid.risk_level ?? "unverified") === risk) &&
        (!needle || `${bid.bid_id} ${bid.bidder_name} ${bid.tender_title}`.toLowerCase().includes(needle)),
    );
    const sign = sort.dir === "asc" ? 1 : -1;
    return rows.sort((a, b) =>
      sort.key === "score"
        ? sign * ((toNumber(a.overall_score) ?? -1) - (toNumber(b.overall_score) ?? -1))
        : sign * a.bid_id.localeCompare(b.bid_id),
    );
  }, [inTender, status, risk, query, sort]);

  const toggleSort = (key: SortKey) =>
    setSort((current) => ({ key, dir: current.key === key && current.dir === "asc" ? "desc" : "asc" }));

  const awaitingDecision = inTender.filter((bid) => bid.status === "submitted" || bid.status === "under_review").length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Bids</h1>
        <p className="mt-1 text-sm text-slate-500">
          {bids === null && !error
            ? "Loading…"
            : `${inTender.length} bids · ${awaitingDecision} awaiting an officer decision`}
        </p>
      </div>

      {error && (
        <Card className="border-red-200 bg-red-50 px-5 py-4 text-sm text-red-800">Failed to load bids: {error}</Card>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {RISK_ORDER.map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setRisk((current) => (current === key ? "all" : key))}
            aria-pressed={risk === key}
            className={cn(
              "rounded-lg border border-l-4 bg-white px-4 py-3 text-left shadow-sm transition hover:bg-slate-50",
              RISK_TILE[key].className,
              risk === key ? "ring-2 ring-slate-900" : "border-slate-200",
            )}
          >
            <div className="text-2xl font-semibold tabular-nums text-slate-900">{riskCounts[key]}</div>
            <div className="text-xs text-slate-500">{RISK_TILE[key].label}</div>
          </button>
        ))}
      </div>

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-4 py-3">
          <label className="relative min-w-[14rem] flex-1">
            <span className="sr-only">Search bids</span>
            <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" aria-hidden />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search bid, bidder or tender"
              className="h-9 w-full rounded-md border border-slate-300 pl-8 pr-3 text-sm focus:border-slate-500 focus:outline-none"
            />
          </label>
          <select
            aria-label="Filter by tender"
            value={tender}
            onChange={(event) => setTender(event.target.value)}
            className="h-9 max-w-xs rounded-md border border-slate-300 bg-white px-2 text-sm"
          >
            <option value="all">All tenders</option>
            {tenders.map(([id, title]) => (
              <option key={id} value={id}>
                {id} — {title}
              </option>
            ))}
          </select>
          <select
            aria-label="Filter by status"
            value={status}
            onChange={(event) => setStatus(event.target.value as BidStatus | "all")}
            className="h-9 rounded-md border border-slate-300 bg-white px-2 text-sm"
          >
            <option value="all">All statuses</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>

        {/* Phones get cards: seven columns can't fit in 390px without hiding the score. */}
        <ul className="divide-y divide-slate-100 md:hidden">
          {visible.map((bid) => (
            <li key={bid.bid_id}>
              <a href={bidHref(bid.bid_id)} className="block px-4 py-3 hover:bg-slate-50">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-medium text-slate-900">{bid.bidder_name}</div>
                    <div className="truncate text-xs text-slate-500">{bid.tender_title}</div>
                    <div className="font-mono text-[11px] text-slate-400">{bid.bid_id}</div>
                  </div>
                  <ScoreCell score={toNumber(bid.overall_score)} />
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <RiskBadge risk={bid.risk_level} />
                  <StatusBadge status={bid.status} />
                </div>
              </a>
            </li>
          ))}
          {bids !== null && visible.length === 0 && (
            <li className="px-4 py-10 text-center text-sm text-slate-500">No bids match these filters.</li>
          )}
        </ul>

        <div className="hidden overflow-x-auto md:block">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <SortHeader label="Bid" active={sort.key === "bid"} dir={sort.dir} onClick={() => toggleSort("bid")} />
                <th className="px-4 py-2.5 font-medium">Bidder</th>
                <th className="px-4 py-2.5 font-medium">Tender</th>
                <SortHeader
                  label="Score"
                  active={sort.key === "score"}
                  dir={sort.dir}
                  onClick={() => toggleSort("score")}
                  className="text-right"
                />
                <th className="px-4 py-2.5 font-medium">Risk</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="w-8" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {visible.map((bid) => (
                <tr
                  key={bid.bid_id}
                  onClick={() => (window.location.hash = bidHref(bid.bid_id))}
                  className="cursor-pointer hover:bg-slate-50"
                >
                  <td className="px-4 py-3">
                    <a href={bidHref(bid.bid_id)} className="font-mono text-xs text-slate-700 hover:underline">
                      {bid.bid_id}
                    </a>
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900">{bid.bidder_name}</div>
                    <div className="text-xs text-slate-500">{bid.enterprise_category ?? "—"} enterprise</div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-slate-800">{bid.tender_title}</div>
                    <div className="font-mono text-xs text-slate-500">{bid.tender_id}</div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <ScoreCell score={toNumber(bid.overall_score)} />
                  </td>
                  <td className="px-4 py-3">
                    <RiskBadge risk={bid.risk_level} />
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={bid.status} />
                  </td>
                  <td className="pr-3 text-slate-400">
                    <ChevronRight className="h-4 w-4" aria-hidden />
                  </td>
                </tr>
              ))}
              {bids !== null && visible.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-sm text-slate-500">
                    No bids match these filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function SortHeader({
  label,
  active,
  dir,
  onClick,
  className,
}: {
  label: string;
  active: boolean;
  dir: "asc" | "desc";
  onClick: () => void;
  className?: string;
}) {
  const Icon = !active ? ArrowUpDown : dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th className={cn("px-4 py-2.5 font-medium", className)} aria-sort={active ? (dir === "asc" ? "ascending" : "descending") : "none"}>
      <button type="button" onClick={onClick} className="inline-flex items-center gap-1 uppercase hover:text-slate-800">
        {label}
        <Icon className="h-3 w-3" aria-hidden />
      </button>
    </th>
  );
}

function ScoreCell({ score }: { score: number | null }) {
  if (score === null) return <span className="text-slate-400">—</span>;
  const color = score >= 85 ? "bg-emerald-500" : score >= 60 ? "bg-amber-400" : "bg-red-500";
  return (
    <div className="inline-flex items-center gap-2">
      <span className="font-semibold tabular-nums text-slate-900">{formatScore(score)}</span>
      <span className="hidden h-1.5 w-14 overflow-hidden rounded-full bg-slate-100 sm:block" aria-hidden>
        <span className={cn("block h-full", color)} style={{ width: `${Math.max(score, 2)}%` }} />
      </span>
    </div>
  );
}
