import { FileSearch, Fingerprint, History, Link2, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ActivityFeed } from "@/components/ActivityFeed";
import { AuditIntegrity } from "@/components/AuditIntegrity";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type RecentAuditEntry } from "@/lib/api";
import { overviewHref } from "@/lib/router";

const PAGE = 25;

const HOW_IT_WORKS = [
  { icon: Fingerprint, title: "Every event is hashed", body: "Each verification result and officer decision is stored with a SHA-256 hash of its full contents." },
  { icon: Link2, title: "Hashes are chained", body: "Every entry's hash also covers the previous entry's hash, so the log for a bid forms a single chain." },
  { icon: ShieldCheck, title: "Edits break the chain", body: "Changing or deleting any past entry changes its hash and breaks every link after it — which the check above detects." },
];

export default function AuditPage() {
  const [entries, setEntries] = useState<RecentAuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [shown, setShown] = useState(PAGE);

  // The API caps at 100; fetch that once and page through it client-side.
  const load = useCallback(() => {
    setError(null);
    api.recentActivity(100).then(setEntries, (cause: Error) => setError(cause.message));
  }, []);
  useEffect(load, [load]);

  return (
    <div className="page-enter space-y-6">
      <PageHeader
        crumbs={[{ label: "Overview", href: overviewHref }, { label: "Audit trail" }]}
        title="Audit trail"
        description="A tamper-evident record of every verification run and officer decision."
      />

      <AuditIntegrity />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            icon={<History className="h-4 w-4" />}
            title="Activity log"
            description="Every verification run and officer decision across all bids, newest first."
          />
          <div className="px-5 py-5">
            {error ? (
              <ErrorState title="Couldn't load the activity log" message={error} onRetry={load} />
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
              <EmptyState icon={FileSearch} title="No audit entries yet">
                Entries appear when a bid is verified or an officer records a decision.
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

        <Card className="h-fit">
          <CardHeader icon={<Fingerprint className="h-4 w-4" />} title="How tamper evidence works" />
          <ol className="space-y-4 px-5 py-5">
            {HOW_IT_WORKS.map(({ icon: Icon, title, body }, i) => (
              <li key={title} className="flex gap-3">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-semibold text-brand-700 ring-1 ring-inset ring-brand-100">
                  {i + 1}
                </span>
                <div>
                  <div className="flex items-center gap-1.5 text-sm font-medium text-slate-900">
                    <Icon className="h-3.5 w-3.5 text-slate-400" aria-hidden />
                    {title}
                  </div>
                  <p className="mt-0.5 text-[13px] leading-snug text-slate-500">{body}</p>
                </div>
              </li>
            ))}
          </ol>
        </Card>
      </div>
    </div>
  );
}
