import { ArrowDown, ArrowUp, ArrowUpDown, ChevronRight, Search, SearchX, X } from "lucide-react";
import { useMemo, useState } from "react";
import { RiskBadge, StatusBadge } from "@/components/badges";
import { EmptyState } from "@/components/States";
import { Card } from "@/components/ui/card";
import { toNumber, type BidStatus, type DashboardBid } from "@/lib/api";
import { formatDate, formatScore, initials, STATUS_LABELS } from "@/lib/format";
import { RISK_KEYS, RISK_STYLE, scoreColor, type RiskKey } from "@/lib/risk";
import { bidHref, navigate } from "@/lib/router";
import { cn } from "@/lib/utils";

export type StatusFilter = BidStatus | "awaiting" | "all";
export type RiskFilter = RiskKey | "flagged" | "all";
type SortKey = "default" | "bidder" | "score" | "submitted";

const AWAITING = new Set<BidStatus>(["submitted", "under_review"]);

const riskMatches = (filter: RiskFilter, key: RiskKey) =>
  filter === "all" || filter === key || (filter === "flagged" && (key === "High" || key === "Non-Compliant"));

export function ParticipantsTable({
  bids,
  showTenderColumn = false,
  initialStatus = "all",
  initialRisk = "all",
}: {
  bids: DashboardBid[];
  showTenderColumn?: boolean;
  initialStatus?: StatusFilter;
  initialRisk?: RiskFilter;
}) {
  const [status, setStatus] = useState<StatusFilter>(initialStatus);
  const [risk, setRisk] = useState<RiskFilter>(initialRisk);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({ key: "default", dir: "asc" });

  const riskCounts = useMemo(() => {
    const counts = Object.fromEntries(RISK_KEYS.map((key) => [key, 0])) as Record<RiskKey, number>;
    bids.forEach((bid) => counts[bid.risk_level ?? "unverified"]++);
    return counts;
  }, [bids]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const rows = bids.filter(
      (bid) =>
        (status === "all" || (status === "awaiting" ? AWAITING.has(bid.status) : bid.status === status)) &&
        riskMatches(risk, bid.risk_level ?? "unverified") &&
        (!needle || `${bid.bid_id} ${bid.bidder_name} ${bid.tender_title} ${bid.tender_id}`.toLowerCase().includes(needle)),
    );
    const sign = sort.dir === "asc" ? 1 : -1;
    return rows.sort((a, b) =>
      sort.key === "score"
        ? sign * ((toNumber(a.overall_score) ?? -1) - (toNumber(b.overall_score) ?? -1))
        : sort.key === "submitted"
          ? sign * a.submitted_at.localeCompare(b.submitted_at)
          : sort.key === "bidder"
            ? sign * a.bidder_name.localeCompare(b.bidder_name)
            : a.bid_id.localeCompare(b.bid_id),
    );
  }, [bids, status, risk, query, sort]);

  const toggleSort = (key: SortKey) =>
    setSort((current) => ({ key, dir: current.key === key && current.dir === "asc" ? "desc" : "asc" }));

  const filtered = status !== "all" || risk !== "all" || query.trim() !== "";
  const clearFilters = () => {
    setStatus("all");
    setRisk("all");
    setQuery("");
  };
  const columns = showTenderColumn ? 7 : 6;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {RISK_KEYS.map((key) => {
          const pressed = risk !== "all" && riskMatches(risk, key);
          return (
            <button
              key={key}
              type="button"
              onClick={() => setRisk((current) => (current === key ? "all" : key))}
              aria-pressed={pressed}
              className={cn(
                "flex items-center gap-3 rounded-xl border bg-white px-4 py-3 text-left shadow-card transition hover:border-slate-300",
                pressed ? "border-brand-400 ring-4 ring-brand-100" : "border-slate-200/80",
              )}
            >
              <span className={cn("h-8 w-1.5 shrink-0 rounded-full", RISK_STYLE[key].dot)} aria-hidden />
              <span>
                <span className="block text-xl font-semibold tabular-nums leading-tight text-slate-900">{riskCounts[key]}</span>
                <span className="block text-xs text-slate-500">{RISK_STYLE[key].label}</span>
              </span>
            </button>
          );
        })}
      </div>

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-4 py-3">
          <label className="relative min-w-[14rem] flex-1">
            <span className="sr-only">Search bids</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={showTenderColumn ? "Search bidder, bid ID or tender" : "Search bidder or bid ID"}
              className="h-9 w-full rounded-lg border border-slate-300 pl-9 pr-3 text-sm placeholder:text-slate-400 focus:border-brand-400 focus:outline-none focus:ring-4 focus:ring-brand-100"
            />
          </label>
          <select
            aria-label="Filter by status"
            value={status}
            onChange={(event) => setStatus(event.target.value as StatusFilter)}
            className="h-9 rounded-lg border border-slate-300 bg-white px-2.5 text-sm text-slate-700 focus:border-brand-400 focus:outline-none focus:ring-4 focus:ring-brand-100"
          >
            <option value="all">All statuses</option>
            <option value="awaiting">Awaiting decision</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <span className="text-[13px] text-slate-500">
            {visible.length} of {bids.length}
          </span>
          {filtered && (
            <button
              type="button"
              onClick={clearFilters}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[13px] font-medium text-brand-700 hover:bg-brand-50"
            >
              <X className="h-3.5 w-3.5" aria-hidden /> Clear filters
            </button>
          )}
        </div>

        {/* Phones get cards: too many columns to fit in 390px without hiding the score. */}
        <ul className="divide-y divide-slate-100 md:hidden">
          {visible.map((bid) => (
            <li key={bid.bid_id}>
              <a href={bidHref(bid.bid_id)} className="flex gap-3 px-4 py-3.5 hover:bg-slate-50">
                <Avatar name={bid.bidder_name} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate font-medium text-slate-900">{bid.bidder_name}</div>
                      {showTenderColumn && <div className="truncate text-xs text-slate-500">{bid.tender_title}</div>}
                      <div className="font-mono text-[11px] text-slate-400">{bid.bid_id}</div>
                    </div>
                    <ScoreCell score={toNumber(bid.overall_score)} />
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <RiskBadge risk={bid.risk_level} />
                    <StatusBadge status={bid.status} />
                  </div>
                </div>
              </a>
            </li>
          ))}
        </ul>

        <div className="hidden overflow-x-auto md:block">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50/80 text-xs text-slate-500">
              <tr>
                <SortHeader label="Bidder" active={sort.key === "bidder"} dir={sort.dir} onClick={() => toggleSort("bidder")} />
                {showTenderColumn && <th className="px-4 py-3 font-medium">Tender</th>}
                <SortHeader label="Score" active={sort.key === "score"} dir={sort.dir} onClick={() => toggleSort("score")} />
                <th className="px-4 py-3 font-medium">Risk</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <SortHeader label="Submitted" active={sort.key === "submitted"} dir={sort.dir} onClick={() => toggleSort("submitted")} />
                <th className="w-10" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {visible.map((bid) => (
                <tr key={bid.bid_id} onClick={() => navigate(bidHref(bid.bid_id))} className="group cursor-pointer transition hover:bg-brand-50/40">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <Avatar name={bid.bidder_name} />
                      <div className="min-w-0">
                        <a
                          href={bidHref(bid.bid_id)}
                          onClick={(event) => event.stopPropagation()}
                          className="block truncate font-medium text-slate-900 hover:text-brand-700"
                        >
                          {bid.bidder_name}
                        </a>
                        <div className="whitespace-nowrap text-xs text-slate-500">
                          <span className="font-mono">{bid.bid_id}</span> · {bid.enterprise_category ?? "—"}
                        </div>
                      </div>
                    </div>
                  </td>
                  {showTenderColumn && (
                    <td className="max-w-[18rem] px-4 py-3">
                      <div className="truncate text-slate-800">{bid.tender_title}</div>
                      <div className="font-mono text-xs text-slate-500">{bid.tender_id}</div>
                    </td>
                  )}
                  <td className="px-4 py-3">
                    <ScoreCell score={toNumber(bid.overall_score)} />
                  </td>
                  <td className="px-4 py-3">
                    <RiskBadge risk={bid.risk_level} />
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={bid.status} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-[13px] text-slate-500" title={formatDate(bid.submitted_at)}>
                    {new Date(bid.submitted_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                  </td>
                  <td className="pr-4 text-slate-300">
                    <ChevronRight className="h-4 w-4 transition group-hover:translate-x-0.5 group-hover:text-slate-500" aria-hidden />
                  </td>
                </tr>
              ))}
              {visible.length === 0 && (
                <tr>
                  <td colSpan={columns}>
                    <EmptyState icon={SearchX} title="No bids match these filters">
                      {filtered && (
                        <button type="button" onClick={clearFilters} className="font-medium text-brand-700 hover:underline">
                          Clear filters
                        </button>
                      )}
                    </EmptyState>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {visible.length === 0 && (
          <div className="md:hidden">
            <EmptyState icon={SearchX} title="No bids match these filters" />
          </div>
        )}
      </Card>
    </div>
  );
}

function Avatar({ name }: { name: string }) {
  return (
    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600 ring-1 ring-inset ring-slate-200">
      {initials(name)}
    </span>
  );
}

function SortHeader({ label, active, dir, onClick }: { label: string; active: boolean; dir: "asc" | "desc"; onClick: () => void }) {
  const Icon = !active ? ArrowUpDown : dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th className="px-4 py-3 font-medium" aria-sort={active ? (dir === "asc" ? "ascending" : "descending") : "none"}>
      <button type="button" onClick={onClick} className={cn("inline-flex items-center gap-1 hover:text-slate-800", active && "text-slate-800")}>
        {label}
        <Icon className="h-3 w-3" aria-hidden />
      </button>
    </th>
  );
}

function ScoreCell({ score }: { score: number | null }) {
  if (score === null) return <span className="text-[13px] text-slate-400">Not scored</span>;
  return (
    <div className="inline-flex items-center gap-2.5">
      <span className="hidden h-1.5 w-16 overflow-hidden rounded-full bg-slate-100 sm:block" aria-hidden>
        <span className={cn("block h-full rounded-full", scoreColor(score))} style={{ width: `${Math.max(score, 3)}%` }} />
      </span>
      <span className="font-semibold tabular-nums text-slate-900">{formatScore(score)}</span>
    </div>
  );
}
