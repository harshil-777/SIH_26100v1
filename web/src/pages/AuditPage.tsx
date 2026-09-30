import { ArrowUpRight, FileSearch, Fingerprint, History, Link2, ShieldAlert, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ActivityFeed } from "@/components/ActivityFeed";
import { AuditIntegrity } from "@/components/AuditIntegrity";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/States";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type AuditVerification, type RecentAuditEntry, type TenderAuditSummary } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { hashParam, overviewHref, tenderAuditHref, tenderHref } from "@/lib/router";
import { cn } from "@/lib/utils";

const PAGE = 25;

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
  const current = tenders?.find((t) => t.tender_id === selected) ?? null;

  return (
    <div className="page-enter space-y-6">
      <PageHeader
        crumbs={[{ label: "Overview", href: overviewHref }, { label: "Audit trail" }]}
        title="Audit trail"
        description="A tamper-evident record of every verification run and officer decision, organised by tender."
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
            <TenderAuditLog key={current.tender_id} tender={current} broken={verification ? brokenTenders.has(current.tender_id) : null} />
          ) : (
            <Card>{tenders ? <EmptyState icon={FileSearch} title="No tenders yet" /> : <Skeleton className="m-5 h-96" />}</Card>
          )}
        </div>
      )}
    </div>
  );
}

function TenderAuditLog({ tender, broken }: { tender: TenderAuditSummary; broken: boolean | null }) {
  const [entries, setEntries] = useState<RecentAuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [shown, setShown] = useState(PAGE);

  const load = useCallback(() => {
    setError(null);
    api.recentActivity(200, tender.tender_id).then(setEntries, (cause: Error) => setError(cause.message));
  }, [tender.tender_id]);
  useEffect(load, [load]);

  return (
    <Card className="h-fit">
      <CardHeader
        icon={<History className="h-4 w-4" />}
        title={tender.title}
        description={`${tender.department} · ${tender.tender_id}`}
        action={
          <a
            href={tenderHref(tender.tender_id)}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[13px] font-medium text-brand-700 hover:bg-brand-50"
          >
            Open tender <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
          </a>
        }
      />
      <div className="grid grid-cols-2 gap-px border-b border-slate-100 bg-slate-100 sm:grid-cols-4">
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
        <div className="bg-white px-5 py-3">
          <div className="text-xs text-slate-500">Hash chains</div>
          <div className="mt-1">
            {broken === null ? (
              <Skeleton className="h-5 w-16" />
            ) : broken ? (
              <Badge tone="critical">Broken</Badge>
            ) : (
              <Badge tone="success">Intact</Badge>
            )}
          </div>
        </div>
      </div>
      <div className="px-5 py-5">
        {error ? (
          <ErrorState title="Couldn't load this tender's activity" message={error} onRetry={load} />
        ) : !entries ? (
          <div className="space-y-5">
            {Array.from({ length: 6 }, (_, i) => (
              <div key={i} className="flex gap-3">
                <Skeleton className="h-8 w-8 rounded-full" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-4 w-1/2" />
                  <Skeleton className="h-3 w-1/3" />
                </div>
              </div>
            ))}
          </div>
        ) : entries.length === 0 ? (
          <EmptyState icon={FileSearch} title="No audit entries for this tender yet">
            Entries appear when one of its bids is verified or an officer records a decision.
          </EmptyState>
        ) : (
          <>
            <ActivityFeed entries={entries.slice(0, shown)} />
            {shown < entries.length && (
              <div className="mt-5 border-t border-slate-100 pt-4 text-center">
                <Button variant="outline" size="sm" onClick={() => setShown((n) => n + PAGE)}>
                  Show more · {entries.length - shown} older
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </Card>
  );
}
