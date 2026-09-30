import { FileStack, Loader2, Search, UserRound } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { RiskBadge } from "@/components/badges";
import { api, type DashboardBid, type TenderListItem } from "@/lib/api";
import { bidHref, navigate, tenderHref } from "@/lib/router";
import { cn } from "@/lib/utils";

type Index = { tenders: TenderListItem[]; bids: DashboardBid[] };
type Result = { key: string; href: string; kind: "tender" | "bid"; title: string; subtitle: string; bid?: DashboardBid };

// Loaded on first focus and shared across mounts; a failed load is dropped so the next focus retries.
let indexPromise: Promise<Index> | null = null;
function loadIndex(): Promise<Index> {
  indexPromise ??= Promise.all([api.listTenders(), api.listBids()])
    .then(([tenders, bids]) => ({ tenders, bids }))
    .catch((error: unknown) => {
      indexPromise = null;
      throw error;
    });
  return indexPromise;
}

const matches = (needle: string, ...fields: (string | null)[]) =>
  fields.some((field) => field?.toLowerCase().includes(needle));

export function GlobalSearch() {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [index, setIndex] = useState<Index | null>(null);
  const [failed, setFailed] = useState(false);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => {
      const typing = event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement;
      if ((event.key === "k" && (event.metaKey || event.ctrlKey)) || (event.key === "/" && !typing)) {
        event.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function onFocus() {
    setOpen(true);
    if (index) return;
    setFailed(false);
    loadIndex().then(setIndex, () => setFailed(true));
  }

  const results = useMemo<Result[]>(() => {
    const needle = query.trim().toLowerCase();
    if (!needle || !index) return [];
    const tenders = index.tenders
      .filter((t) => matches(needle, t.title, t.tender_id, t.department, t.category))
      .slice(0, 4)
      .map<Result>((t) => ({
        key: `t:${t.tender_id}`,
        href: tenderHref(t.tender_id),
        kind: "tender",
        title: t.title,
        subtitle: `${t.tender_id} · ${t.department}`,
      }));
    const bids = index.bids
      .filter((b) => matches(needle, b.bidder_name, b.bid_id, b.tender_title, b.tender_id))
      .slice(0, 6)
      .map<Result>((b) => ({
        key: `b:${b.bid_id}`,
        href: bidHref(b.bid_id),
        kind: "bid",
        title: b.bidder_name,
        subtitle: `${b.bid_id} · ${b.tender_title}`,
        bid: b,
      }));
    return [...tenders, ...bids];
  }, [query, index]);

  useEffect(() => setActive(0), [query]);

  function go(result: Result) {
    navigate(result.href);
    setQuery("");
    setOpen(false);
    inputRef.current?.blur();
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      setOpen(false);
      inputRef.current?.blur();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter" && results[active]) {
      event.preventDefault();
      go(results[active]);
    }
  }

  const showPanel = open && (query.trim() !== "" || failed);

  return (
    <div className="relative">
      <label className="relative block">
        <span className="sr-only">Search tenders, bidders and bids</span>
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
        <input
          ref={inputRef}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onFocus={onFocus}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
          placeholder="Search tenders, bidders, bid IDs…"
          role="combobox"
          aria-expanded={showPanel}
          aria-controls="global-search-results"
          aria-autocomplete="list"
          className="h-10 w-full rounded-lg border border-slate-200 bg-slate-50/80 pl-9 pr-14 text-sm text-slate-900 placeholder:text-slate-400 transition focus:border-brand-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-brand-100"
        />
        <kbd className="pointer-events-none absolute right-2.5 top-1/2 hidden -translate-y-1/2 rounded border border-slate-200 bg-white px-1.5 py-0.5 font-sans text-[11px] font-medium text-slate-400 sm:block">
          Ctrl K
        </kbd>
      </label>

      {showPanel && (
        <div
          id="global-search-results"
          role="listbox"
          className="absolute left-0 right-0 top-12 z-50 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lift animate-in fade-in-0 zoom-in-95 duration-100"
          onMouseDown={(event) => event.preventDefault()}
        >
          {failed ? (
            <p className="px-4 py-6 text-center text-sm text-slate-500">Search is unavailable — the API could not be reached.</p>
          ) : !index ? (
            <p className="flex items-center justify-center gap-2 px-4 py-6 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Loading…
            </p>
          ) : results.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-slate-500">No tenders or bids match “{query.trim()}”.</p>
          ) : (
            <ul className="max-h-[22rem] overflow-y-auto py-1.5">
              {results.map((result, i) => {
                const Icon = result.kind === "tender" ? FileStack : UserRound;
                const header = i === 0 || results[i - 1].kind !== result.kind;
                return (
                  <li key={result.key}>
                    {header && (
                      <div className="px-4 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                        {result.kind === "tender" ? "Tenders" : "Bids"}
                      </div>
                    )}
                    <button
                      type="button"
                      role="option"
                      aria-selected={i === active}
                      onMouseEnter={() => setActive(i)}
                      onClick={() => go(result)}
                      className={cn("flex w-full items-center gap-3 px-4 py-2 text-left", i === active && "bg-brand-50")}
                    >
                      <span
                        className={cn(
                          "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
                          result.kind === "tender" ? "bg-slate-100 text-slate-600" : "bg-brand-50 text-brand-700",
                        )}
                      >
                        <Icon className="h-4 w-4" aria-hidden />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-slate-900">{result.title}</span>
                        <span className="block truncate text-xs text-slate-500">{result.subtitle}</span>
                      </span>
                      {result.bid && <RiskBadge risk={result.bid.risk_level} />}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
