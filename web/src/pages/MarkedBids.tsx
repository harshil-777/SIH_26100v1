import { Bookmark, BookmarkX, ChevronRight, FileStack, Loader2, StickyNote } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { RiskBadge, StatusBadge } from "@/components/badges";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/States";
import { LinkButton } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, toNumber, type MarkedBid } from "@/lib/api";
import { formatDateTime, formatRelative, formatScore, initials } from "@/lib/format";
import { scoreColor } from "@/lib/risk";
import { bidHref, overviewHref, tendersHref } from "@/lib/router";
import { cn } from "@/lib/utils";

export default function MarkedBids() {
  const [marks, setMarks] = useState<MarkedBid[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    api.listMarks().then(setMarks, (cause: Error) => setError(cause.message));
  }, []);
  useEffect(load, [load]);

  const removed = (bidId: string) => setMarks((current) => current?.filter((m) => m.bid_id !== bidId) ?? null);

  return (
    <div className="page-enter">
      <PageHeader
        crumbs={[{ label: "Overview", href: overviewHref }, { label: "Marked bids" }]}
        title="Marked bids"
        description={
          marks
            ? `${marks.length} ${marks.length === 1 ? "bid" : "bids"} flagged to check later. Mark bids from a tender's participant list.`
            : "Bids flagged to check later. Mark bids from a tender's participant list."
        }
      />

      {error ? (
        <ErrorState title="Couldn't load marked bids" message={error} onRetry={load} />
      ) : !marks ? (
        <Card className="space-y-4 p-5">
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </Card>
      ) : marks.length === 0 ? (
        <Card>
          <EmptyState icon={Bookmark} title="No marked bids yet">
            <p>Open a tender and use the bookmark icon on a bidder's row to keep it here for later.</p>
            <LinkButton href={tendersHref} variant="outline" size="sm" className="mt-4">
              <FileStack className="h-4 w-4" aria-hidden /> Browse tenders
            </LinkButton>
          </EmptyState>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <ul className="divide-y divide-slate-100">
            {marks.map((mark) => (
              <MarkedRow key={mark.bid_id} mark={mark} onRemoved={() => removed(mark.bid_id)} />
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

function MarkedRow({ mark, onRemoved }: { mark: MarkedBid; onRemoved: () => void }) {
  const [busy, setBusy] = useState(false);
  const score = toNumber(mark.overall_score);

  async function unmark() {
    setBusy(true);
    try {
      await api.unmarkBid(mark.bid_id);
      onRemoved();
    } catch {
      setBusy(false);
    }
  }

  return (
    <li className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:gap-5">
      <a href={bidHref(mark.bid_id)} className="group flex min-w-0 flex-1 items-center gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-50 text-sm font-semibold text-brand-700 ring-1 ring-inset ring-brand-100">
          {initials(mark.bidder_name)}
        </span>
        <span className="min-w-0">
          <span className="block truncate font-medium text-slate-900 group-hover:text-brand-700">{mark.bidder_name}</span>
          <span className="block truncate text-xs text-slate-500">
            <span className="font-mono">{mark.bid_id}</span> · {mark.tender_title}
          </span>
          {mark.note && (
            <span className="mt-1 flex items-start gap-1 text-[13px] text-slate-600">
              <StickyNote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" aria-hidden />
              <span className="line-clamp-2">{mark.note}</span>
            </span>
          )}
        </span>
      </a>

      <div className="flex items-center gap-2.5 sm:w-24">
        {score === null ? (
          <span className="text-[13px] text-slate-400">Not scored</span>
        ) : (
          <>
            <span className="h-1.5 w-12 overflow-hidden rounded-full bg-slate-100" aria-hidden>
              <span className={cn("block h-full rounded-full", scoreColor(score))} style={{ width: `${Math.max(score, 3)}%` }} />
            </span>
            <span className="text-sm font-semibold tabular-nums text-slate-900">{formatScore(score)}</span>
          </>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5 sm:w-auto">
        <RiskBadge risk={mark.risk_level} />
        <StatusBadge status={mark.status} />
      </div>

      <div className="text-xs text-slate-500 sm:w-40" title={formatDateTime(mark.marked_at)}>
        Marked {formatRelative(mark.marked_at)}
        <span className="block truncate">by {mark.marked_by}</span>
      </div>

      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={unmark}
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[13px] font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-60"
          aria-label={`Unmark ${mark.bidder_name}`}
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : <BookmarkX className="h-3.5 w-3.5" aria-hidden />}
          Unmark
        </button>
        <a href={bidHref(mark.bid_id)} className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="Open bid">
          <ChevronRight className="h-4 w-4" />
        </a>
      </div>
    </li>
  );
}
