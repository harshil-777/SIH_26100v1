import {
  ArrowRight,
  CalendarClock,
  ChevronRight,
  ClipboardCheck,
  FileSearch,
  FileStack,
  Fingerprint,
  Gavel,
  History,
  Landmark,
  ScanText,
  ShieldAlert,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityFeed } from "@/components/ActivityFeed";
import { RiskBadge } from "@/components/badges";
import { RiskBar, RiskKeyLegend } from "@/components/RiskVisuals";
import { StatCard } from "@/components/StatCard";
import { EmptyState, ErrorState } from "@/components/States";
import { LinkButton } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, toNumber, type DashboardBid, type RecentAuditEntry, type TenderListItem } from "@/lib/api";
import { daysUntil, deadlineLabel, deadlineTone, formatInrCompact, formatScore, initials } from "@/lib/format";
import { RISK_KEYS, riskRank, scoreColor, type RiskKey } from "@/lib/risk";
import { auditHref, bidHref, tenderHref, tendersHref } from "@/lib/router";
import { cn } from "@/lib/utils";

type Data = { tenders: TenderListItem[]; bids: DashboardBid[] };

const AWAITING = new Set(["submitted", "under_review"]);

const PILLARS = [
  { icon: Gavel, title: "Eligibility rules", body: "MSME, Make in India, EPFO and debarment criteria applied per tender" },
  { icon: Landmark, title: "Registry checks", body: "GSTN, Udyam, PAN, MCA21 and EPFO responses compared with declarations" },
  { icon: ScanText, title: "Document AI", body: "OCR and a trained extractor read every uploaded certificate" },
  { icon: Fingerprint, title: "Tamper-evident trail", body: "Each decision is SHA-256 hash-chained to the one before it" },
];

export default function Overview() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activity, setActivity] = useState<RecentAuditEntry[] | null>(null);

  const load = useCallback(() => {
    setError(null);
    Promise.all([api.listTenders(), api.listBids()]).then(
      ([tenders, bids]) => setData({ tenders, bids }),
      (cause: Error) => setError(cause.message),
    );
    // Separate so a failure here only empties the feed rather than the whole page.
    api.recentActivity(5).then(setActivity, () => setActivity([]));
  }, []);

  useEffect(load, [load]);

  const stats = useMemo(() => {
    if (!data) return null;
    const open = data.tenders.filter((t) => daysUntil(t.submission_deadline) >= 0);
    const verified = data.bids.filter((b) => b.risk_level !== null);
    const counts = Object.fromEntries(RISK_KEYS.map((key) => [key, 0])) as Record<RiskKey, number>;
    data.bids.forEach((b) => counts[b.risk_level ?? "unverified"]++);
    const scores = verified.map((b) => toNumber(b.overall_score) ?? 0);
    return {
      open,
      openValue: open.reduce((sum, t) => sum + (toNumber(t.estimated_value_inr) ?? 0), 0),
      verified: verified.length,
      awaiting: data.bids.filter((b) => AWAITING.has(b.status)),
      flagged: counts["Non-Compliant"] + counts.High,
      counts,
      averageScore: scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null,
    };
  }, [data]);

  const queue = useMemo(
    () =>
      (stats?.awaiting ?? [])
        .slice()
        .sort((a, b) => riskRank(a.risk_level) - riskRank(b.risk_level) || (toNumber(a.overall_score) ?? 101) - (toNumber(b.overall_score) ?? 101))
        .slice(0, 8),
    [stats],
  );

  const closingSoon = useMemo(
    () => (stats?.open ?? []).slice().sort((a, b) => a.submission_deadline.localeCompare(b.submission_deadline)).slice(0, 5),
    [stats],
  );

  return (
    <div className="page-enter space-y-6">
      <Hero />

      {error ? (
        <ErrorState title="Couldn't load the dashboard" message={error} onRetry={load} />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Open tenders"
              icon={FileStack}
              loading={!stats}
              value={stats?.open.length}
              hint={stats && `${formatInrCompact(stats.openValue)} total estimated value`}
              href={tendersHref}
            />
            <StatCard
              label="Bids received"
              icon={Users}
              tone="slate"
              loading={!stats}
              value={data?.bids.length}
              hint={stats && `${stats.verified} verified · avg score ${stats.averageScore === null ? "—" : formatScore(Math.round(stats.averageScore * 10) / 10)}`}
            />
            <StatCard
              label="Awaiting decision"
              icon={ClipboardCheck}
              tone="amber"
              loading={!stats}
              value={stats?.awaiting.length}
              hint="Submitted or under review"
            />
            <StatCard
              label="Flagged bids"
              icon={ShieldAlert}
              tone="red"
              loading={!stats}
              value={stats?.flagged}
              hint="High risk or non-compliant"
            />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader
                icon={<ClipboardCheck className="h-4 w-4" />}
                title="Review queue"
                description="Bids awaiting an officer decision across all tenders — highest risk first."
              />
              {!stats ? (
                <ListSkeleton rows={5} />
              ) : queue.length === 0 ? (
                <EmptyState icon={ClipboardCheck} title="All caught up">
                  Every bid has an officer decision on record.
                </EmptyState>
              ) : (
                <ul className="divide-y divide-slate-100">
                  {queue.map((bid) => (
                    <QueueRow key={bid.bid_id} bid={bid} />
                  ))}
                </ul>
              )}
            </Card>

            <Card>
              <CardHeader
                icon={<ShieldAlert className="h-4 w-4" />}
                title="Risk by tender"
                description="How each tender's bids split across risk levels — most flagged first."
              />
              <div className="px-5 py-5">
                {!data ? (
                  <div className="space-y-5">
                    {Array.from({ length: 5 }, (_, i) => (
                      <Skeleton key={i} className="h-9 w-full" />
                    ))}
                  </div>
                ) : (
                  <TenderRiskList tenders={data.tenders} />
                )}
              </div>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader
                icon={<CalendarClock className="h-4 w-4" />}
                title="Closing soon"
                description="Open tenders by submission deadline."
                action={<ViewAll href={tendersHref} label="All tenders" />}
              />
              {!stats ? (
                <ListSkeleton rows={4} />
              ) : closingSoon.length === 0 ? (
                <EmptyState icon={CalendarClock} title="No open tenders" />
              ) : (
                <ul className="divide-y divide-slate-100">
                  {closingSoon.map((tender) => (
                    <ClosingRow key={tender.tender_id} tender={tender} />
                  ))}
                </ul>
              )}
            </Card>

            <Card>
              <CardHeader
                icon={<History className="h-4 w-4" />}
                title="Recent activity"
                action={<ViewAll href={auditHref} label="Audit trail" />}
              />
              <div className="px-5 py-5">
                {activity === null ? (
                  <ListSkeleton rows={4} bare />
                ) : activity.length === 0 ? (
                  <EmptyState icon={FileSearch} title="No activity yet" />
                ) : (
                  <ActivityFeed entries={activity} dense />
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

function TenderRiskList({ tenders }: { tenders: TenderListItem[] }) {
  const flaggedShare = (t: TenderListItem) =>
    t.participant_count ? (t.risk_counts["Non-Compliant"] + t.risk_counts.High) / t.participant_count : 0;
  const sorted = tenders.slice().sort((a, b) => flaggedShare(b) - flaggedShare(a));
  return (
    <>
      <RiskKeyLegend />
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

function QueueRow({ bid }: { bid: DashboardBid }) {
  const score = toNumber(bid.overall_score);
  return (
    <li>
      <a href={bidHref(bid.bid_id)} className="group flex items-center gap-4 px-5 py-3.5 transition hover:bg-slate-50">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-100 text-sm font-semibold text-slate-600">
          {initials(bid.bidder_name)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-slate-900">{bid.bidder_name}</span>
          <span className="block truncate text-[13px] text-slate-500">{bid.tender_title}</span>
          <span className="mt-1.5 block sm:hidden">
            <RiskBadge risk={bid.risk_level} />
          </span>
        </span>
        <span className="hidden w-32 sm:block">
          {score === null ? (
            <span className="text-xs text-slate-400">Not scored</span>
          ) : (
            <span className="flex items-center gap-2">
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                <span className={cn("block h-full rounded-full", scoreColor(score))} style={{ width: `${Math.max(score, 3)}%` }} />
              </span>
              <span className="w-10 text-right text-sm font-semibold tabular-nums text-slate-900">{formatScore(Math.round(score))}</span>
            </span>
          )}
        </span>
        <span className="hidden sm:inline-flex">
          <RiskBadge risk={bid.risk_level} />
        </span>
        <ChevronRight className="h-4 w-4 shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-slate-500" aria-hidden />
      </a>
    </li>
  );
}

function ClosingRow({ tender }: { tender: TenderListItem }) {
  return (
    <li>
      <a href={tenderHref(tender.tender_id)} className="group grid gap-3 px-5 py-3.5 transition hover:bg-slate-50 sm:grid-cols-[minmax(0,1fr)_9rem_8rem] sm:items-center">
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium text-slate-900">{tender.title}</span>
          <span className="block truncate text-[13px] text-slate-500">
            {tender.department} · {formatInrCompact(toNumber(tender.estimated_value_inr) ?? 0)}
          </span>
        </span>
        <span className="text-[13px]">
          <span className={cn("block font-medium", deadlineTone(tender.submission_deadline))}>{deadlineLabel(tender.submission_deadline)}</span>
          <span className="block text-slate-500">
            {tender.participant_count} bidder{tender.participant_count === 1 ? "" : "s"}
          </span>
        </span>
        <RiskBar counts={tender.risk_counts} />
      </a>
    </li>
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
