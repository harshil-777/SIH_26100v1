import { ArrowUpRight, Building2, CalendarClock, FileSearch, IndianRupee, Search, Users } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { RiskBadge } from "@/components/badges";
import { PageHeader } from "@/components/PageHeader";
import { RiskBar } from "@/components/RiskVisuals";
import { EmptyState, ErrorState } from "@/components/States";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, toNumber, type TenderListItem } from "@/lib/api";
import { deadlineLabel, deadlineTone, formatDate, formatInrCompact, formatScore } from "@/lib/format";
import { riskRank } from "@/lib/risk";
import { overviewHref, tenderHref } from "@/lib/router";
import { cn } from "@/lib/utils";

type Category = "all" | "Goods" | "Services";
type SortKey = "deadline" | "value" | "participants" | "risk";

const SORTS: Record<SortKey, { label: string; compare: (a: TenderListItem, b: TenderListItem) => number }> = {
  deadline: { label: "Deadline (soonest)", compare: (a, b) => a.submission_deadline.localeCompare(b.submission_deadline) },
  value: { label: "Value (highest)", compare: (a, b) => (toNumber(b.estimated_value_inr) ?? 0) - (toNumber(a.estimated_value_inr) ?? 0) },
  participants: { label: "Most bidders", compare: (a, b) => b.participant_count - a.participant_count },
  risk: { label: "Risk (worst first)", compare: (a, b) => riskRank(a.worst_risk_level) - riskRank(b.worst_risk_level) },
};

export default function TenderList() {
  const [tenders, setTenders] = useState<TenderListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<Category>("all");
  const [sort, setSort] = useState<SortKey>("deadline");

  const load = useCallback(() => {
    setError(null);
    api.listTenders().then(setTenders, (cause: Error) => setError(cause.message));
  }, []);
  useEffect(load, [load]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (tenders ?? [])
      .filter((t) => category === "all" || t.category === category)
      .filter((t) => !needle || `${t.title} ${t.tender_id} ${t.department}`.toLowerCase().includes(needle))
      .sort(SORTS[sort].compare);
  }, [tenders, query, category, sort]);

  const totalValue = (tenders ?? []).reduce((sum, t) => sum + (toNumber(t.estimated_value_inr) ?? 0), 0);

  return (
    <div className="page-enter">
      <PageHeader
        crumbs={[{ label: "Overview", href: overviewHref }, { label: "Tenders" }]}
        title="Tenders"
        description={
          tenders
            ? `${tenders.length} tenders under compliance review · ${formatInrCompact(totalValue)} combined estimated value`
            : "Tenders under compliance review"
        }
      />

      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center">
        <label className="relative flex-1 sm:max-w-sm">
          <span className="sr-only">Search tenders</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by title, ID or department"
            className="h-10 w-full rounded-lg border border-slate-300 bg-white pl-9 pr-3 text-sm shadow-sm placeholder:text-slate-400 focus:border-brand-400 focus:outline-none focus:ring-4 focus:ring-brand-100"
          />
        </label>

        <div className="inline-flex rounded-lg border border-slate-300 bg-white p-0.5 shadow-sm" role="group" aria-label="Category">
          {(["all", "Goods", "Services"] as Category[]).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setCategory(value)}
              aria-pressed={category === value}
              className={cn(
                "rounded-md px-3.5 py-1.5 text-sm font-medium transition",
                category === value ? "bg-brand-600 text-white shadow-sm" : "text-slate-600 hover:text-slate-900",
              )}
            >
              {value === "all" ? "All" : value}
            </button>
          ))}
        </div>

        <select
          aria-label="Sort tenders"
          value={sort}
          onChange={(event) => setSort(event.target.value as SortKey)}
          className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700 shadow-sm focus:border-brand-400 focus:outline-none focus:ring-4 focus:ring-brand-100 sm:ml-auto"
        >
          {Object.entries(SORTS).map(([key, { label }]) => (
            <option key={key} value={key}>
              Sort: {label}
            </option>
          ))}
        </select>
      </div>

      {error ? (
        <ErrorState title="Couldn't load tenders" message={error} onRetry={load} />
      ) : !tenders ? (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => (
            <Card key={i} className="space-y-4 p-5">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-5 w-4/5" />
              <Skeleton className="h-3.5 w-1/2" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-2 w-full" />
            </Card>
          ))}
        </div>
      ) : visible.length === 0 ? (
        <Card>
          <EmptyState icon={FileSearch} title="No tenders match these filters">
            Try a different search term or category.
          </EmptyState>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
          {visible.map((tender) => (
            <TenderCard key={tender.tender_id} tender={tender} />
          ))}
        </div>
      )}
    </div>
  );
}

function TenderCard({ tender }: { tender: TenderListItem }) {
  const average = toNumber(tender.average_score);
  const verified = tender.participant_count - tender.risk_counts.unverified;

  return (
    <a
      href={tenderHref(tender.tender_id)}
      className="group flex flex-col rounded-xl border border-slate-200/80 bg-white p-5 shadow-card transition hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-lift"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone={tender.category === "Goods" ? "brand" : "info"}>{tender.category}</Badge>
          {tender.msme_reserved && <Badge tone="success">MSME reserved</Badge>}
        </div>
        <ArrowUpRight className="h-4 w-4 text-slate-300 transition group-hover:text-brand-600" aria-hidden />
      </div>

      <h2 className="mt-3 line-clamp-2 text-base font-semibold leading-snug tracking-tight text-slate-900 group-hover:text-brand-800">
        {tender.title}
      </h2>
      <div className="mt-1 flex items-center gap-1.5 text-[13px] text-slate-500">
        <Building2 className="h-3.5 w-3.5 shrink-0" aria-hidden />
        <span className="truncate">{tender.department}</span>
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-3 rounded-lg bg-slate-50 px-3 py-3">
        <Fact icon={IndianRupee} label="Value" value={formatInrCompact(toNumber(tender.estimated_value_inr) ?? 0)} />
        <Fact icon={Users} label="Bidders" value={String(tender.participant_count)} />
        <Fact
          icon={CalendarClock}
          label="Deadline"
          value={formatDate(tender.submission_deadline).replace(/ \d{4}$/, "")}
          title={formatDate(tender.submission_deadline)}
        />
      </dl>

      <div className="mt-4 flex-1">
        <div className="mb-1.5 flex items-center justify-between text-xs">
          <span className="font-medium text-slate-600">Bid risk profile</span>
          <span className="text-slate-500">
            {verified}/{tender.participant_count} verified{average !== null && ` · avg ${formatScore(Math.round(average))}`}
          </span>
        </div>
        <RiskBar counts={tender.risk_counts} />
      </div>

      <div className="mt-4 flex items-center justify-between gap-2 border-t border-slate-100 pt-3.5 text-[13px]">
        <span className={cn("font-medium", deadlineTone(tender.submission_deadline))}>{deadlineLabel(tender.submission_deadline)}</span>
        {tender.awaiting_decision_count > 0 ? (
          <span className="font-medium text-amber-700">{tender.awaiting_decision_count} awaiting decision</span>
        ) : tender.worst_risk_level ? (
          <RiskBadge risk={tender.worst_risk_level} />
        ) : null}
      </div>
      <div className="mt-2 font-mono text-[11px] text-slate-400">{tender.tender_id}</div>
    </a>
  );
}

function Fact({ icon: Icon, label, value, title }: { icon: typeof Users; label: string; value: string; title?: string }) {
  return (
    <div className="min-w-0" title={title}>
      <dt className="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">
        <Icon className="h-3 w-3" aria-hidden />
        {label}
      </dt>
      <dd className="mt-0.5 truncate text-sm font-semibold text-slate-900">{value}</dd>
    </div>
  );
}
