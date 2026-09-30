import { BarChart3, Building2, CalendarClock, FileCheck2, Gauge, History, IndianRupee, ListChecks, Scale, Users } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { RiskBadge } from "@/components/badges";
import { PageHeader } from "@/components/PageHeader";
import { ParticipantsTable } from "@/components/ParticipantsTable";
import { StatCard } from "@/components/StatCard";
import { EmptyState, ErrorState } from "@/components/States";
import { Badge } from "@/components/ui/badge";
import { LinkButton } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError, toNumber, type DashboardBid, type DocumentRequirement, type TenderOut } from "@/lib/api";
import { criterionLabel, deadlineLabel, formatDate, formatInr, formatInrCompact, formatScore, initials } from "@/lib/format";
import { RISK_STYLE, riskRank } from "@/lib/risk";
import { bidHref, overviewHref, tenderAuditHref, tendersHref } from "@/lib/router";
import { cn } from "@/lib/utils";

type Data = { tender: TenderOut; bids: DashboardBid[]; requirements: DocumentRequirement[] };

const SOURCE_LABEL: Record<string, string> = {
  buyer_atc: "Buyer ATC",
  system_template: "GeM bid template",
  buyer_selected_turnover_experience: "Buyer-selected eligibility",
};

export default function TenderDetail({ tenderId }: { tenderId: string }) {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);

  const load = useCallback(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    Promise.all([api.getTender(tenderId), api.listBids(tenderId), api.getDocumentRequirements(tenderId).catch(() => [])])
      .then(([tender, bids, requirements]) => !cancelled && setData({ tender, bids, requirements }))
      .catch((cause: unknown) => {
        if (!cancelled) setError({ status: cause instanceof ApiError ? cause.status : 0, message: (cause as Error).message });
      });
    return () => {
      cancelled = true;
    };
  }, [tenderId]);

  useEffect(load, [load]);

  const crumbs = [
    { label: "Overview", href: overviewHref },
    { label: "Tenders", href: tendersHref },
    { label: tenderId },
  ];

  if (error) {
    return (
      <div className="page-enter">
        <PageHeader crumbs={crumbs} title="Tender" />
        <ErrorState
          title={error.status === 404 ? "Tender not found" : "Couldn't load this tender"}
          message={error.status === 404 ? `There is no tender with ID ${tenderId}.` : error.message}
          onRetry={error.status === 404 ? undefined : load}
        />
      </div>
    );
  }

  if (!data) return <TenderSkeleton />;

  const { tender, bids, requirements } = data;
  return <TenderView tender={tender} bids={bids} requirements={requirements} crumbs={crumbs} />;
}

function TenderView({
  tender,
  bids,
  requirements,
  crumbs,
}: Data & { crumbs: { label: string; href?: string }[] }) {
  const awaiting = bids.filter((bid) => bid.status === "submitted" || bid.status === "under_review").length;
  const scores = bids.map((bid) => toNumber(bid.overall_score)).filter((s): s is number => s !== null);
  const average = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
  const threshold = toNumber(tender.mii_local_content_threshold_pct);

  return (
    <div className="page-enter space-y-6">
      <PageHeader
        crumbs={crumbs}
        title={tender.title}
        actions={
          <LinkButton href={tenderAuditHref(tender.tender_id)} variant="outline">
            <History className="h-4 w-4" aria-hidden /> Audit trail
          </LinkButton>
        }
        meta={
          <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
            <span className="inline-flex items-center gap-1.5">
              <Building2 className="h-4 w-4" aria-hidden />
              {tender.department}
            </span>
            <span className="text-slate-300">·</span>
            <span className="font-mono text-[13px]">{tender.tender_id}</span>
            <span className="text-slate-300">·</span>
            <Badge tone={tender.category === "Goods" ? "brand" : "info"}>{tender.category}</Badge>
            {tender.msme_reserved && <Badge tone="success">MSME reserved</Badge>}
            {threshold !== null && threshold > 0 && <Badge tone="neutral">Make in India ≥{threshold}%</Badge>}
            {tender.requires_oem_authorization && <Badge tone="neutral">OEM authorization</Badge>}
            {tender.epfo_applicable_employee_threshold !== null && (
              <Badge tone="neutral">EPFO ≥{tender.epfo_applicable_employee_threshold} staff</Badge>
            )}
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Estimated value"
          icon={IndianRupee}
          value={formatInrCompact(toNumber(tender.estimated_value_inr) ?? 0)}
          hint={formatInr(toNumber(tender.estimated_value_inr) ?? 0)}
        />
        <StatCard
          label="Submission deadline"
          icon={CalendarClock}
          tone="amber"
          value={formatDate(tender.submission_deadline).replace(/ \d{4}$/, "")}
          hint={deadlineLabel(tender.submission_deadline)}
        />
        <StatCard label="Bidders" icon={Users} tone="slate" value={bids.length} hint={`${awaiting} awaiting a decision`} />
        <StatCard
          label="Average score"
          icon={Gauge}
          tone="emerald"
          value={average === null ? "—" : formatScore(Math.round(average * 10) / 10)}
          hint={`${scores.length} of ${bids.length} bids verified`}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3 lg:items-start">
        <Card className="lg:col-span-2">
          <CardHeader
            icon={<BarChart3 className="h-4 w-4" />}
            title="Bidder comparison"
            description="Participants ranked by compliance score. Colour shows the risk verdict."
          />
          <BidderRanking bids={bids} />
        </Card>

        <Card>
          <CardHeader icon={<Scale className="h-4 w-4" />} title="Scoring rubric" description="How this tender's bids are evaluated." />
          <Rubric tender={tender} />
        </Card>
      </div>

      <section>
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <h2 className="text-lg font-semibold tracking-tight text-slate-900">
            Participants <span className="font-normal text-slate-400">({bids.length})</span>
          </h2>
        </div>
        <ParticipantsTable bids={bids} />
      </section>

      <Card>
        <CardHeader
          icon={<FileCheck2 className="h-4 w-4" />}
          title="Required documents"
          description="What every bidder must upload for this tender, and where each requirement comes from."
        />
        {requirements.length === 0 ? (
          <EmptyState icon={ListChecks} title="No document requirements recorded" />
        ) : (
          <ul className="grid gap-px bg-slate-100 sm:grid-cols-2">
            {requirements.map((req, i) => (
              <li
                key={req.requirement_id}
                // An odd count would otherwise leave an empty grey cell showing through the gap-px grid.
                className={cn("bg-white px-5 py-4", requirements.length % 2 === 1 && i === requirements.length - 1 && "sm:col-span-2")}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="text-sm font-medium text-slate-900">{req.buyer_label ?? req.document_type}</div>
                  <Badge tone={req.mandatory ? "danger" : "neutral"}>{req.mandatory ? "Mandatory" : "Conditional"}</Badge>
                </div>
                {req.notes && <p className="mt-1 text-[13px] leading-snug text-slate-500">{req.notes}</p>}
                <div className="mt-2 text-xs text-slate-400">
                  Source: {SOURCE_LABEL[req.requirement_source] ?? req.requirement_source.replace(/_/g, " ")}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function BidderRanking({ bids }: { bids: DashboardBid[] }) {
  const ranked = useMemo(
    () =>
      bids
        .slice()
        .sort((a, b) => (toNumber(b.overall_score) ?? -1) - (toNumber(a.overall_score) ?? -1) || riskRank(a.risk_level) - riskRank(b.risk_level)),
    [bids],
  );
  if (ranked.length === 0) return <EmptyState icon={Users} title="No bids received yet" />;

  return (
    <ol className="space-y-1 px-3 py-3">
      {ranked.map((bid, i) => {
        const score = toNumber(bid.overall_score);
        const style = RISK_STYLE[bid.risk_level ?? "unverified"];
        return (
          <li key={bid.bid_id}>
            <a href={bidHref(bid.bid_id)} className="group grid grid-cols-[1.5rem_2.25rem_minmax(0,1fr)] items-center gap-3 rounded-lg px-2 py-2.5 transition hover:bg-slate-50 sm:grid-cols-[1.5rem_2.25rem_15rem_minmax(0,1fr)_auto]">
              <span className="text-center text-sm font-semibold tabular-nums text-slate-400">{i + 1}</span>
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600">
                {initials(bid.bidder_name)}
              </span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-slate-900 group-hover:text-brand-700">{bid.bidder_name}</span>
                <span className="block font-mono text-[11px] text-slate-400">{bid.bid_id}</span>
              </span>
              <span className="col-span-3 flex items-center gap-3 sm:col-span-1">
                <span className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                  {score !== null && (
                    <span className="block h-full rounded-full" style={{ width: `${Math.max(score, 3)}%`, backgroundColor: style.hex }} />
                  )}
                </span>
                <span className="w-12 text-right text-sm font-semibold tabular-nums text-slate-900">
                  {score === null ? <span className="font-normal text-slate-400">—</span> : formatScore(Math.round(score * 10) / 10)}
                </span>
              </span>
              <span className="hidden sm:block">
                <RiskBadge risk={bid.risk_level} />
              </span>
            </a>
          </li>
        );
      })}
    </ol>
  );
}

function Rubric({ tender }: { tender: TenderOut }) {
  const criteria = tender.eligibility_rules_json?.criteria ?? [];
  const mandatory = criteria.filter((c) => c.type === "mandatory");
  const graded = criteria.filter((c) => c.type === "graded");
  const totalWeight = graded.reduce((sum, c) => sum + (c.weight ?? 0), 0);

  if (criteria.length === 0) return <EmptyState icon={Scale} title="No eligibility rules recorded" />;

  return (
    <div className="space-y-5 px-5 py-4">
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Mandatory · pass or fail</div>
        <ul className="mt-2 space-y-1.5">
          {mandatory.map((c) => (
            <li key={c.id} className="flex items-center gap-2 text-sm text-slate-700">
              <span className="h-1.5 w-1.5 rounded-full bg-red-500" aria-hidden />
              {criterionLabel(c.id)}
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-slate-500">Any failure caps the score at 40 and marks the bid non-compliant.</p>
      </div>
      {graded.length > 0 && (
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Graded · weighted</div>
          <ul className="mt-2 space-y-2.5">
            {graded.map((c) => {
              const pct = totalWeight ? Math.round(((c.weight ?? 0) / totalWeight) * 100) : 0;
              return (
                <li key={c.id}>
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <span className="text-slate-700">{criterionLabel(c.id)}</span>
                    <span className="font-semibold tabular-nums text-slate-900">{pct}%</span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <span className="block h-full rounded-full bg-brand-500" style={{ width: `${pct}%` }} />
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

function TenderSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-5 w-1/2" />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <StatCard key={i} label="" icon={Users} loading value={null} />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3 lg:items-start">
        <Card className={cn("h-64 lg:col-span-2")}>
          <Skeleton className="m-5 h-40" />
        </Card>
        <Card className="h-64">
          <Skeleton className="m-5 h-40" />
        </Card>
      </div>
    </div>
  );
}
