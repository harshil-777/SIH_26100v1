import { ArrowUpRight, ChevronDown, FileSearch, Fingerprint, History, Link2, Search, ShieldAlert, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityFeed } from "@/components/ActivityFeed";
import { AuditIntegrity } from "@/components/AuditIntegrity";
import { RiskBadge, StatusBadge } from "@/components/badges";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type AuditVerification, type DashboardBid, type RecentAuditEntry, type TenderAuditSummary } from "@/lib/api";
import { formatRelative, initials } from "@/lib/format";
import { bidHref, hashParam, overviewHref, tenderAuditHref, tenderHref } from "@/lib/router";
import { cn } from "@/lib/utils";

const HOW_IT_WORKS = [
  { icon: Fingerprint, title: "Every event is hashed", body: "Each verification result and officer decision is stored with a SHA-256 hash of its full contents." },
  { icon: Link2, title: "Hashes are chained", body: "Every entry's hash also covers the previous entry's hash, so each bid's log forms a single chain." },
  { icon: ShieldCheck, title: "Edits break the chain", body: "Changing or deleting any past entry breaks every link after it — which the integrity check detects." },
];

export default function AuditPage() {
  const [tenders, setTenders] = useState<TenderAuditSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(() => hashParam("tender"));
  const [verification, setVerification] = useState<AuditVerification | null>(null);

  const load = useCallback(() => {
    setError(null);
    api.auditByTender().then(
      (rows) => {
        setTenders(rows);
        setSelected((current) => (current && rows.some((t) => t.tender_id === current) ? current : rows[0]?.tender_id ?? null));
      },
      (cause: Error) => setError(cause.message),
    );
  }, []);
  useEffect(load, [load]);

  // Keep the URL shareable without a hashchange (which would remount the page).
  function select(tenderId: string) {
    setSelected(tenderId);
    window.history.replaceState(null, "", tenderAuditHref(tenderId));
  }

  const brokenTenders = new Set((verification?.breaks ?? []).map((b) => b.tender_id).filter(Boolean));
  const brokenBids = verification ? new Set(verification.breaks.map((b) => b.bid_id).filter((id): id is string => Boolean(id))) : null;
  const current = tenders?.find((t) => t.tender_id === selected) ?? null;

  return (
    <div className="page-enter space-y-6">
      <PageHeader
        crumbs={[{ label: "Overview", href: overviewHref }, { label: "Audit trail" }]}
        title="Audit trail"
        description="A tamper-evident record of every verification run and officer decision. Pick a tender to see its trail bid by bid."
      />

      <AuditIntegrity onResult={setVerification} />

      {error ? (
        <ErrorState title="Couldn't load the audit trail" message={error} onRetry={load} />
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
          <div className="space-y-6">
            <Card>
              <CardHeader icon={<History className="h-4 w-4" />} title="Tenders" description="Select a tender to see its audit history." />
              {!tenders ? (
                <div className="space-y-3 p-4">
                  {Array.from({ length: 6 }, (_, i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : (
                <ul className="space-y-1 p-2" role="listbox" aria-label="Tenders">
                  {tenders.map((tender) => {
                    const active = tender.tender_id === selected;
                    const broken = brokenTenders.has(tender.tender_id);
                    return (
                      <li key={tender.tender_id}>
                        <button
                          type="button"
                          role="option"
                          aria-selected={active}
                          onClick={() => select(tender.tender_id)}
                          className={cn(
                            "w-full rounded-lg border px-3 py-2.5 text-left transition",
                            active ? "border-brand-300 bg-brand-50/70 ring-2 ring-brand-100" : "border-transparent hover:bg-slate-50",
                          )}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <span className={cn("line-clamp-2 text-sm font-medium", active ? "text-brand-900" : "text-slate-900")}>
                              {tender.title}
                            </span>
                            {verification &&
                              (broken ? (
                                <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-red-600" aria-label="Chain broken" />
                              ) : (
                                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" aria-label="Chain intact" />
                              ))}
                          </div>
                          <div className="mt-1 flex flex-wrap items-center gap-x-2 text-xs text-slate-500">
                            <span className="font-mono">{tender.tender_id}</span>
                            <span>·</span>
                            <span>{tender.entry_count} entries</span>
                            {tender.last_activity_at && (
                              <>
                                <span>·</span>
                                <span>{formatRelative(tender.last_activity_at)}</span>
                              </>
                            )}
                          </div>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </Card>

            <Card className="hidden lg:block">
              <CardHeader icon={<Fingerprint className="h-4 w-4" />} title="How tamper evidence works" />
              <ol className="space-y-4 px-5 py-5">
                {HOW_IT_WORKS.map(({ title, body }, i) => (
                  <li key={title} className="flex gap-3">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-semibold text-brand-700 ring-1 ring-inset ring-brand-100">
                      {i + 1}
                    </span>
                    <div>
                      <div className="text-sm font-medium text-slate-900">{title}</div>
                      <p className="mt-0.5 text-[13px] leading-snug text-slate-500">{body}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </Card>
          </div>

          {current ? (
            <TenderBidTrails key={current.tender_id} tender={current} brokenBids={brokenBids} />
          ) : (
            <Card>{tenders ? <EmptyState icon={FileSearch} title="No tenders yet" /> : <Skeleton className="m-5 h-96" />}</Card>
          )}
        </div>
      )}
    </div>
  );
}

// The selected tender's trail, grouped by bid: each bid's own hash-chained history in one card.
function TenderBidTrails({ tender, brokenBids }: { tender: TenderAuditSummary; brokenBids: Set<string> | null }) {
  const [data, setData] = useState<{ bids: DashboardBid[]; entries: RecentAuditEntry[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<Set<string>>(new Set());

  const load = useCallback(() => {
    setError(null);
    Promise.all([api.listBids(tender.tender_id), api.recentActivity(1000, tender.tender_id)]).then(
      ([bids, entries]) => setData({ bids, entries }),
      (cause: Error) => setError(cause.message),
    );
  }, [tender.tender_id]);
  useEffect(load, [load]);

  const trails = useMemo(() => {
    if (!data) return [];
    const byBid = new Map<string, RecentAuditEntry[]>();
    for (const entry of data.entries) {
      if (!entry.bid_id) continue;
      byBid.set(entry.bid_id, [...(byBid.get(entry.bid_id) ?? []), entry]);
    }
    const needle = query.trim().toLowerCase();
    return data.bids
      .filter((bid) => !needle || `${bid.bidder_name} ${bid.bid_id}`.toLowerCase().includes(needle))
      .map((bid) => ({ bid, entries: byBid.get(bid.bid_id) ?? [] }))
      .sort((a, b) => (b.entries[0]?.timestamp ?? "").localeCompare(a.entries[0]?.timestamp ?? ""));
  }, [data, query]);

  const toggle = (bidId: string) =>
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(bidId)) next.delete(bidId);
      else next.add(bidId);
      return next;
    });
  const allOpen = trails.length > 0 && trails.every((t) => open.has(t.bid.bid_id));

  return (
    <Card className="h-fit">
      <CardHeader
        icon={<History className="h-4 w-4" />}
        title={tender.title}
        description={`${tender.department} · ${tender.tender_id} · audit trail by bid`}
        action={
          <a
            href={tenderHref(tender.tender_id)}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[13px] font-medium text-brand-700 hover:bg-brand-50"
          >
            Open tender <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
          </a>
        }
      />
      <div className="grid grid-cols-3 gap-px border-b border-slate-100 bg-slate-100">
        {[
          ["Bids", tender.bid_count],
          ["Verifications", tender.verification_count],
          ["Officer decisions", tender.decision_count],
        ].map(([label, value]) => (
          <div key={label} className="bg-white px-5 py-3">
            <div className="text-xs text-slate-500">{label}</div>
            <div className="text-lg font-semibold tabular-nums text-slate-900">{value}</div>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-4 py-3">
        <label className="relative min-w-[12rem] flex-1">
          <span className="sr-only">Search bids</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search bidder or bid ID"
            className="h-9 w-full rounded-lg border border-slate-300 pl-9 pr-3 text-sm placeholder:text-slate-400 focus:border-brand-400 focus:outline-none focus:ring-4 focus:ring-brand-100"
          />
        </label>
        <Button variant="outline" size="sm" onClick={() => setOpen(allOpen ? new Set() : new Set(trails.map((t) => t.bid.bid_id)))} disabled={!trails.length}>
          {allOpen ? "Collapse all" : "Expand all"}
        </Button>
      </div>

      {error ? (
        <div className="p-5">
          <ErrorState title="Couldn't load this tender's audit trail" message={error} onRetry={load} />
        </div>
      ) : !data ? (
        <div className="space-y-3 p-4">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : trails.length === 0 ? (
        <EmptyState icon={FileSearch} title={query ? "No bids match your search" : "No bids on this tender yet"} />
      ) : (
        <ul className="divide-y divide-slate-100">
          {trails.map(({ bid, entries }) => (
            <BidTrail
              key={bid.bid_id}
              bid={bid}
              entries={entries}
              broken={brokenBids ? brokenBids.has(bid.bid_id) : null}
              open={open.has(bid.bid_id)}
              onToggle={() => toggle(bid.bid_id)}
            />
          ))}
        </ul>
      )}
    </Card>
  );
}

function BidTrail({
  bid,
  entries,
  broken,
  open,
  onToggle,
}: {
  bid: DashboardBid;
  entries: RecentAuditEntry[];
  broken: boolean | null;
  open: boolean;
  onToggle: () => void;
}) {
  const verifications = entries.filter((e) => e.action === "verify_completed").length;
  const decisions = entries.filter((e) => e.action === "officer_decision").length;
  return (
    <li>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className={cn("flex w-full items-center gap-3 px-5 py-3.5 text-left transition hover:bg-slate-50", open && "bg-slate-50/70")}
      >
        <ChevronDown className={cn("h-4 w-4 shrink-0 text-slate-400 transition-transform", !open && "-rotate-90")} aria-hidden />
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600">
          {initials(bid.bidder_name)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-slate-900">{bid.bidder_name}</span>
          <span className="block truncate text-xs text-slate-500">
            <span className="font-mono">{bid.bid_id}</span> · {verifications} verification{verifications === 1 ? "" : "s"} · {decisions}{" "}
            decision{decisions === 1 ? "" : "s"}
            {entries[0] && <> · last {formatRelative(entries[0].timestamp)}</>}
          </span>
        </span>
        <span className="hidden flex-wrap justify-end gap-1.5 sm:flex">
          <RiskBadge risk={bid.risk_level} />
          <StatusBadge status={bid.status} />
        </span>
        {broken === null ? null : broken ? (
          <ShieldAlert className="h-4 w-4 shrink-0 text-red-600" aria-label="Hash chain broken" />
        ) : (
          <ShieldCheck className="h-4 w-4 shrink-0 text-emerald-600" aria-label="Hash chain intact" />
        )}
      </button>
      {open && (
        <div className="border-t border-slate-100 bg-slate-50/40 px-5 py-4 pl-[4.25rem]">
          {entries.length === 0 ? (
            <p className="text-sm text-slate-500">No audit entries for this bid yet.</p>
          ) : (
            <ActivityFeed entries={entries} dense showBid={false} />
          )}
          <a href={bidHref(bid.bid_id)} className="mt-3 inline-flex items-center gap-1 text-[13px] font-medium text-brand-700 hover:underline">
            Open bid <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
          </a>
        </div>
      )}
    </li>
  );
}
