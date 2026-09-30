import {
  ArrowRight,
  Bookmark,
  ChevronRight,
  ClipboardCheck,
  FileSearch,
  Fingerprint,
  Gavel,
  History,
  Landmark,
  ScanText,
  ShieldAlert,
  StickyNote,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityFeed } from "@/components/ActivityFeed";
import { RiskBadge, StatusBadge } from "@/components/badges";
import { RiskBar } from "@/components/RiskVisuals";
import { StatCard } from "@/components/StatCard";
import { EmptyState, ErrorState } from "@/components/States";
import { LinkButton } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, toNumber, type DashboardBid, type MarkedBid, type RecentAuditEntry, type TenderListItem } from "@/lib/api";
import { formatRelative, formatScore, initials } from "@/lib/format";
import { RISK_KEYS, riskRank, RISK_STYLE, scoreColor, type RiskKey } from "@/lib/risk";
import { auditHref, bidHref, markedHref, tenderHref, tendersHref } from "@/lib/router";
import { cn } from "@/lib/utils";

const AWAITING = new Set(["submitted", "under_review"]);

const PILLARS = [
  { icon: Gavel, title: "Eligibility rules", body: "MSME, Make in India, EPFO and debarment criteria applied per tender" },
  { icon: Landmark, title: "Registry checks", body: "GSTN, Udyam, PAN, MCA21 and EPFO responses compared with declarations" },
  { icon: ScanText, title: "Document AI", body: "OCR and a trained extractor read every uploaded certificate" },
  { icon: Fingerprint, title: "Tamper-evident trail", body: "Each decision is SHA-256 hash-chained to the one before it" },
];

export default function Overview() {
  const [bids, setBids] = useState<DashboardBid[] | null>(null);
  const [tenders, setTenders] = useState<TenderListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [marks, setMarks] = useState<MarkedBid[] | null>(null);
  const [activity, setActivity] = useState<RecentAuditEntry[] | null>(null);

  const load = useCallback(() => {
    setError(null);
    Promise.all([api.listBids(), api.listTenders()]).then(
      ([bidRows, tenderRows]) => {
        setBids(bidRows);
        setTenders(tenderRows);
      },
      (cause: Error) => setError(cause.message),
    );
    // Separate so a failure in either only empties its own card rather than the whole page.
    api.listMarks().then(setMarks, () => setMarks([]));
    api.recentActivity(60).then(setActivity, () => setActivity([]));
  }, []);

  useEffect(load, [load]);

  const stats = useMemo(() => {
    if (!bids) return null;
    const verified = bids.filter((b) => b.risk_level !== null);
    const counts = Object.fromEntries(RISK_KEYS.map((key) => [key, 0])) as Record<RiskKey, number>;
    bids.forEach((b) => counts[b.risk_level ?? "unverified"]++);
    const scores = verified.map((b) => toNumber(b.overall_score) ?? 0);
    return {
      verified: verified.length,
      awaiting: bids.filter((b) => AWAITING.has(b.status)),
      flagged: counts["Non-Compliant"] + counts.High,
      counts,
      averageScore: scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null,
    };
  }, [bids]);

  // Grouped by tender, worst-risk tender first; within a tender, worst-risk bid first.
  const queueByTender = useMemo(() => {
    if (!stats) return [];
    const groups = new Map<string, { tenderId: string; tenderTitle: string; bids: DashboardBid[] }>();
    for (const bid of stats.awaiting) {
      const group = groups.get(bid.tender_id) ?? { tenderId: bid.tender_id, tenderTitle: bid.tender_title, bids: [] };
      group.bids.push(bid);
      groups.set(bid.tender_id, group);
    }
    const sortBids = (a: DashboardBid, b: DashboardBid) =>
      riskRank(a.risk_level) - riskRank(b.risk_level) || (toNumber(a.overall_score) ?? 101) - (toNumber(b.overall_score) ?? 101);
    return Array.from(groups.values())
      .map((group) => ({ ...group, bids: group.bids.slice().sort(sortBids) }))
      .sort((a, b) => riskRank(a.bids[0].risk_level) - riskRank(b.bids[0].risk_level) || b.bids.length - a.bids.length);
  }, [stats]);

  // One row per bid: its latest audit event, rather than a stream of events.
  const latestPerBid = useMemo(() => {
    if (!activity) return null;
    const seen = new Set<string>();
    return activity.filter((entry) => entry.bid_id && !seen.has(entry.bid_id) && seen.add(entry.bid_id)).slice(0, 5);
  }, [activity]);

  return (
    <div className="page-enter space-y-6">
      <Hero />

      {error ? (
        <ErrorState title="Couldn't load the dashboard" message={error} onRetry={load} />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Bids received"
              icon={Users}
              tone="slate"
              loading={!stats}
              value={bids?.length}
              hint={stats && `${stats.verified} verified · avg score ${stats.averageScore === null ? "—" : formatScore(Math.round(stats.averageScore * 10) / 10)}`}
            />
            <StatCard label="Awaiting decision" icon={ClipboardCheck} tone="amber" loading={!stats} value={stats?.awaiting.length} hint="Submitted or under review" />
            <StatCard label="Flagged bids" icon={ShieldAlert} tone="red" loading={!stats} value={stats?.flagged} hint="High risk or non-compliant" />
            <StatCard
              label="Marked for later"
              icon={Bookmark}
              loading={marks === null}
              value={marks?.length}
              hint="Bids you flagged to revisit"
              href={markedHref}
            />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3 lg:items-start">
            <Card className="lg:col-span-2">
              <CardHeader
                icon={<ClipboardCheck className="h-4 w-4" />}
                title="Review queue"
                description="Bids awaiting an officer decision, grouped by tender — worst risk first."
              />
              {!stats ? (
                <ListSkeleton rows={6} />
              ) : queueByTender.length === 0 ? (
                <EmptyState icon={ClipboardCheck} title="All caught up">
                  Every bid has an officer decision on record.
                </EmptyState>
              ) : (
                <div className="divide-y divide-slate-100">
                  {queueByTender.map((group) => (
                    <TenderQueueGroup key={group.tenderId} group={group} />
                  ))}
                </div>
              )}
            </Card>

            <Card>
              <CardHeader icon={<ShieldAlert className="h-4 w-4" />} title="Risk by tender" description="How each tender's bids split across risk levels — most flagged first." />
              <div className="px-5 py-5">
                {!tenders ? (
                  <div className="space-y-5">
                    {Array.from({ length: 6 }, (_, i) => (
                      <Skeleton key={i} className="h-9 w-full" />
                    ))}
                  </div>
                ) : (
                  <TenderRiskList tenders={tenders} />
                )}
              </div>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader
                icon={<Bookmark className="h-4 w-4" />}
                title="Marked for later"
                description="Bids you flagged from a tender's participant list."
                action={<ViewAll href={markedHref} label="All marked" />}
              />
              {marks === null ? (
                <ListSkeleton rows={3} />
              ) : marks.length === 0 ? (
                <EmptyState icon={Bookmark} title="Nothing marked yet">
                  Open a tender and use the bookmark icon on a bidder's row.
                </EmptyState>
              ) : (
                <ul className="divide-y divide-slate-100">
                  {marks.slice(0, 5).map((mark) => (
                    <MarkedRow key={mark.bid_id} mark={mark} />
                  ))}
                </ul>
              )}
            </Card>

            <Card>
              <CardHeader
                icon={<History className="h-4 w-4" />}
                title="Latest bid updates"
                description="Most recent audit event for each bid."
                action={<ViewAll href={auditHref} label="Audit trail" />}
              />
              <div className="px-5 py-5">
                {latestPerBid === null ? (
                  <ListSkeleton rows={4} bare />
                ) : latestPerBid.length === 0 ? (
                  <EmptyState icon={FileSearch} title="No activity yet" />
                ) : (
                  <ActivityFeed entries={latestPerBid} dense />
                )}
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function Hero() {
  const today = new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  return (
    <section className="relative overflow-hidden rounded-2xl bg-brand-950 text-white shadow-lift">
      <div className="hero-grid absolute inset-0" aria-hidden />
      <div className="absolute -right-24 -top-24 h-80 w-80 rounded-full bg-brand-600/30 blur-3xl" aria-hidden />
      <div className="absolute -bottom-32 left-1/3 h-72 w-72 rounded-full bg-sky-500/10 blur-3xl" aria-hidden />

      <div className="relative grid gap-8 px-6 py-8 sm:px-8 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:items-center lg:gap-10 lg:px-10 lg:py-10">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.06] px-3 py-1 text-xs font-medium text-slate-300">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" aria-hidden />
            {today}
          </div>
          <h1 className="mt-4 text-[28px] font-semibold leading-tight tracking-tight sm:text-4xl sm:leading-[1.15]">
            Every bid checked against the rules, the documents and the registries.
          </h1>
          <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-slate-300">
            Bid-Auth evaluates Government e-Marketplace bids for eligibility, cross-verifies each declaration against
            uploaded certificates and government registries, and records every officer decision in a tamper-evident audit
            trail.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <LinkButton href={tendersHref} variant="inverse" size="lg">
              Browse tenders <ArrowRight className="h-4 w-4" aria-hidden />
            </LinkButton>
            <LinkButton href={auditHref} variant="inverse-outline" size="lg">
              View audit trail
            </LinkButton>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          {PILLARS.map(({ icon: Icon, title, body }) => (
            <div key={title} className="rounded-xl border border-white/[0.08] bg-white/[0.04] p-3.5 backdrop-blur-sm sm:p-4">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500/20 text-brand-200 ring-1 ring-inset ring-brand-400/30">
                <Icon className="h-4 w-4" aria-hidden />
              </span>
              <div className="mt-3 text-[13px] font-semibold text-white sm:text-sm">{title}</div>
              <p className="mt-1 hidden text-[13px] leading-snug text-slate-400 sm:block">{body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ScoreMeter({ score }: { score: number | null }) {
  if (score === null) return <span className="text-xs text-slate-400">Not scored</span>;
  return (
    <span className="flex items-center gap-2">
      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
        <span className={cn("block h-full rounded-full", scoreColor(score))} style={{ width: `${Math.max(score, 3)}%` }} />
      </span>
      <span className="w-10 text-right text-sm font-semibold tabular-nums text-slate-900">{formatScore(Math.round(score))}</span>
    </span>
  );
}

function MarkedRow({ mark }: { mark: MarkedBid }) {
  return (
    <li>
      <a href={bidHref(mark.bid_id)} className="group flex items-center gap-4 px-5 py-3.5 transition hover:bg-slate-50">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-50 text-sm font-semibold text-brand-700 ring-1 ring-inset ring-brand-100">
          {initials(mark.bidder_name)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-slate-900">{mark.bidder_name}</span>
          <span className="mt-0.5 block truncate text-xs text-slate-500">
            <span className="font-mono">{mark.bid_id}</span> · marked {formatRelative(mark.marked_at)}
          </span>
          {mark.note && (
            <span className="mt-1 flex items-start gap-1 text-[13px] text-slate-600">
              <StickyNote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" aria-hidden />
              <span className="truncate">{mark.note}</span>
            </span>
          )}
        </span>
        <span className="hidden w-32 sm:block">
          <ScoreMeter score={toNumber(mark.overall_score)} />
        </span>
        <span className="hidden flex-col items-end gap-1 md:flex">
          <RiskBadge risk={mark.risk_level} />
          <StatusBadge status={mark.status} />
        </span>
        <ChevronRight className="h-4 w-4 shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-slate-500" aria-hidden />
      </a>
    </li>
  );
}

function TenderQueueGroup({ group }: { group: { tenderId: string; tenderTitle: string; bids: DashboardBid[] } }) {
  const SHOWN = 3;
  const visible = group.bids.slice(0, SHOWN);
  const extra = group.bids.length - visible.length;
  return (
    <div className="px-5 py-3.5">
      <a href={tenderHref(group.tenderId)} className="group flex items-baseline justify-between gap-3">
        <span className="truncate text-sm font-semibold text-slate-900 group-hover:text-brand-700">{group.tenderTitle}</span>
        <span className="shrink-0 text-xs font-medium text-amber-700">
          {group.bids.length} awaiting
        </span>
      </a>
      <ul className="mt-2 space-y-2">
        {visible.map((bid) => (
          <li key={bid.bid_id}>
            <a href={bidHref(bid.bid_id)} className="group/row flex items-center gap-3 rounded-lg px-2 py-1.5 -mx-2 transition hover:bg-slate-50">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600">
                {initials(bid.bidder_name)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm text-slate-800 group-hover/row:text-brand-700">{bid.bidder_name}</span>
                <span className="block truncate font-mono text-[11px] text-slate-400">{bid.bid_id}</span>
              </span>
              <span className="hidden w-28 sm:block">
                <ScoreMeter score={toNumber(bid.overall_score)} />
              </span>
              <RiskBadge risk={bid.risk_level} />
            </a>
          </li>
        ))}
      </ul>
      {extra > 0 && (
        <a href={tenderHref(group.tenderId)} className="mt-2 inline-block text-[13px] font-medium text-brand-700 hover:underline">
          +{extra} more in this tender
        </a>
      )}
    </div>
  );
}

function TenderRiskList({ tenders }: { tenders: TenderListItem[] }) {
  const flaggedShare = (t: TenderListItem) =>
    t.participant_count ? (t.risk_counts["Non-Compliant"] + t.risk_counts.High) / t.participant_count : 0;
  const sorted = tenders.slice().sort((a, b) => flaggedShare(b) - flaggedShare(a));
  return (
    <>
      <ul className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
        {RISK_KEYS.map((key) => (
          <li key={key} className="inline-flex items-center gap-1.5">
            <span className={cn("h-2 w-2 rounded-sm", RISK_STYLE[key].dot)} aria-hidden />
            {RISK_STYLE[key].label}
          </li>
        ))}
      </ul>
      <ul className="mt-4 space-y-4">
        {sorted.map((tender) => (
          <li key={tender.tender_id}>
            <a href={tenderHref(tender.tender_id)} className="group block">
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="truncate font-medium text-slate-800 group-hover:text-brand-700">{tender.title}</span>
                <span className="shrink-0 text-xs tabular-nums text-slate-500">{tender.participant_count} bids</span>
              </div>
              <RiskBar counts={tender.risk_counts} className="mt-1.5 h-2.5" />
              <div className="mt-1 text-xs text-slate-500">
                {Math.round(flaggedShare(tender) * 100)}% flagged · {tender.risk_counts.Low} low risk
              </div>
            </a>
          </li>
        ))}
      </ul>
    </>
  );
}

function ViewAll({ href, label }: { href: string; label: string }) {
  return (
    <a href={href} className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[13px] font-medium text-brand-700 hover:bg-brand-50">
      {label} <ArrowRight className="h-3.5 w-3.5" aria-hidden />
    </a>
  );
}

function ListSkeleton({ rows, bare = false }: { rows: number; bare?: boolean }) {
  return (
    <div className={cn("space-y-4", !bare && "px-5 py-5")}>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-3">
          <Skeleton className="h-9 w-9 rounded-full" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-3.5 w-2/3" />
            <Skeleton className="h-3 w-1/3" />
          </div>
        </div>
      ))}
    </div>
  );
}
