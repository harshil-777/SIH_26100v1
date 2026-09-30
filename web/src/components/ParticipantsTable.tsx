import { ArrowDown, ArrowUp, ArrowUpDown, Bookmark, BookmarkCheck, ChevronRight, Loader2, Search, SearchX, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { RiskBadge, StatusBadge } from "@/components/badges";
import { EmptyState } from "@/components/States";
import { Card } from "@/components/ui/card";
import { api, toNumber, type BidStatus, type DashboardBid } from "@/lib/api";
import { formatDate, formatScore, initials, STATUS_LABELS } from "@/lib/format";
import { readOfficer } from "@/lib/officer";
import { RISK_KEYS, RISK_STYLE, scoreColor, type RiskKey } from "@/lib/risk";
import { bidHref, navigate } from "@/lib/router";
import { cn } from "@/lib/utils";

type StatusFilter = BidStatus | "awaiting" | "all";
type RiskFilter = RiskKey | "all";
type SortKey = "default" | "bidder" | "score" | "submitted";

const AWAITING = new Set<BidStatus>(["submitted", "under_review"]);

const riskMatches = (filter: RiskFilter, key: RiskKey) => filter === "all" || filter === key;

export function ParticipantsTable({ bids }: { bids: DashboardBid[] }) {
  const [status, setStatus] = useState<StatusFilter>("all");
  const [risk, setRisk] = useState<RiskFilter>("all");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({ key: "default", dir: "asc" });
  const [marked, setMarked] = useState(() => new Set(bids.filter((bid) => bid.marked).map((bid) => bid.bid_id)));
  const [markedOnly, setMarkedOnly] = useState(false);

  const setMark = (bidId: string, on: boolean) =>
    setMarked((current) => {
      const next = new Set(current);
      if (on) next.add(bidId);
      else next.delete(bidId);
      return next;
    });

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
        (!markedOnly || marked.has(bid.bid_id)) &&
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
  }, [bids, status, risk, query, sort, markedOnly, marked]);

  const toggleSort = (key: SortKey) =>
    setSort((current) => ({ key, dir: current.key === key && current.dir === "asc" ? "desc" : "asc" }));

  const filtered = status !== "all" || risk !== "all" || query.trim() !== "" || markedOnly;
  const clearFilters = () => {
    setStatus("all");
    setRisk("all");
    setQuery("");
    setMarkedOnly(false);
  };

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
              placeholder="Search bidder or bid ID"
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
          <button
            type="button"
            onClick={() => setMarkedOnly((on) => !on)}
            aria-pressed={markedOnly}
            className={cn(
              "inline-flex h-9 items-center gap-1.5 rounded-lg border px-3 text-sm font-medium transition",
              markedOnly ? "border-brand-400 bg-brand-50 text-brand-800" : "border-slate-300 text-slate-700 hover:bg-slate-50",
            )}
          >
            <BookmarkCheck className="h-4 w-4" aria-hidden />
            Marked only
            <span className="tabular-nums text-slate-500">{marked.size}</span>
          </button>
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
            <li key={bid.bid_id} className="relative flex items-start">
              <a href={bidHref(bid.bid_id)} className="flex min-w-0 flex-1 gap-3 py-3.5 pl-4 hover:bg-slate-50">
                <Avatar name={bid.bidder_name} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate font-medium text-slate-900">{bid.bidder_name}</div>
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
              <div className="px-2 pt-3">
                <MarkButton bidId={bid.bid_id} bidder={bid.bidder_name} marked={marked.has(bid.bid_id)} onChange={(on) => setMark(bid.bid_id, on)} />
              </div>
            </li>
          ))}
        </ul>

        <div className="hidden overflow-x-auto md:block">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50/80 text-xs text-slate-500">
              <tr>
                <SortHeader label="Bidder" active={sort.key === "bidder"} dir={sort.dir} onClick={() => toggleSort("bidder")} />
                <SortHeader label="Score" active={sort.key === "score"} dir={sort.dir} onClick={() => toggleSort("score")} />
                <th className="px-4 py-3 font-medium">Risk</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <SortHeader label="Submitted" active={sort.key === "submitted"} dir={sort.dir} onClick={() => toggleSort("submitted")} />
                <th className="w-12 px-2 py-3 text-center font-medium">
                  <span className="sr-only">Mark for later</span>
                  <Bookmark className="mx-auto h-3.5 w-3.5" aria-hidden />
                </th>
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
                  <td className="px-2 py-3 text-center" onClick={(event) => event.stopPropagation()}>
                    <MarkButton bidId={bid.bid_id} bidder={bid.bidder_name} marked={marked.has(bid.bid_id)} onChange={(on) => setMark(bid.bid_id, on)} />
                  </td>
                  <td className="pr-4 text-slate-300">
                    <ChevronRight className="h-4 w-4 transition group-hover:translate-x-0.5 group-hover:text-slate-500" aria-hidden />
                  </td>
                </tr>
              ))}
              {visible.length === 0 && (
                <tr>
                  <td colSpan={7}>
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

// Marking asks for an optional note ("why check this later?"); unmarking is one click.
function MarkButton({ bidId, bidder, marked, onChange }: { bidId: string; bidder: string; marked: boolean; onChange: (marked: boolean) => void }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  async function unmark() {
    setBusy(true);
    try {
      await api.unmarkBid(bidId);
      onChange(false);
    } catch {
      // Stays marked; the unchanged icon is the feedback.
    } finally {
      setBusy(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.markBid(bidId, { marked_by: readOfficer() || "Procurement officer", note: note.trim() || null });
      onChange(true);
      setOpen(false);
      setNote("");
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => (marked ? unmark() : setOpen((o) => !o))}
        disabled={busy}
        aria-pressed={marked}
        title={marked ? "Marked for later - click to unmark" : "Mark to check later"}
        aria-label={marked ? `Unmark ${bidder}` : `Mark ${bidder} to check later`}
        className={cn(
          "rounded-md p-1.5 transition",
          marked ? "text-brand-600 hover:bg-brand-50" : "text-slate-300 hover:bg-slate-100 hover:text-slate-600",
        )}
      >
        {busy && !open ? (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        ) : marked ? (
          <BookmarkCheck className="h-4 w-4 fill-brand-100" aria-hidden />
        ) : (
          <Bookmark className="h-4 w-4" aria-hidden />
        )}
      </button>
      {open && (
        <form
          onSubmit={submit}
          onKeyDown={(event) => event.key === "Escape" && setOpen(false)}
          className="absolute right-0 top-full z-30 mt-1 w-72 rounded-xl border border-slate-200 bg-white p-3 text-left shadow-lift animate-in fade-in-0 zoom-in-95 duration-100"
        >
          <div className="text-sm font-medium text-slate-900">Mark to check later</div>
          <div className="truncate text-xs text-slate-500">{bidder}</div>
          <input
            ref={inputRef}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Note (optional), e.g. verify EPFO count"
            className="mt-2.5 h-9 w-full rounded-lg border border-slate-300 px-3 text-sm placeholder:text-slate-400 focus:border-brand-400 focus:outline-none focus:ring-4 focus:ring-brand-100"
          />
          {error && <p className="mt-1.5 text-xs text-red-700">{error}</p>}
          <div className="mt-3 flex justify-end gap-2">
            <button type="button" onClick={() => setOpen(false)} className="rounded-md px-3 py-1.5 text-[13px] font-medium text-slate-600 hover:bg-slate-100">
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-md bg-brand-600 px-3 py-1.5 text-[13px] font-medium text-white hover:bg-brand-700 disabled:opacity-60"
            >
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : <Bookmark className="h-3.5 w-3.5" aria-hidden />}
              Mark bid
            </button>
          </div>
        </form>
      )}
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
