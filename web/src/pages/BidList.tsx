import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { ParticipantsTable, type RiskFilter, type StatusFilter } from "@/components/ParticipantsTable";
import { ErrorState } from "@/components/States";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type DashboardBid } from "@/lib/api";
import { hashParam, overviewHref } from "@/lib/router";

export default function BidList() {
  const [bids, setBids] = useState<DashboardBid[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Read once: the overview's cards deep-link here pre-filtered (e.g. #/bids?status=awaiting).
  const [initialStatus] = useState(() => (hashParam("status") ?? "all") as StatusFilter);
  const [initialRisk] = useState(() => (hashParam("risk") ?? "all") as RiskFilter);

  const load = useCallback(() => {
    setError(null);
    api.listBids().then(setBids, (cause: Error) => setError(cause.message));
  }, []);
  useEffect(load, [load]);

  const awaiting = bids?.filter((bid) => bid.status === "submitted" || bid.status === "under_review").length ?? 0;

  return (
    <div className="page-enter">
      <PageHeader
        crumbs={[{ label: "Overview", href: overviewHref }, { label: "Bids" }]}
        title={initialStatus === "awaiting" ? "Review queue" : "All bids"}
        description={
          bids
            ? `${bids.length} bids across all tenders · ${awaiting} awaiting an officer decision`
            : "Every bid across all tenders, with its latest compliance verdict."
        }
      />
      {error ? (
        <ErrorState title="Couldn't load bids" message={error} onRetry={load} />
      ) : !bids ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {Array.from({ length: 5 }, (_, i) => (
              <Skeleton key={i} className="h-[62px] rounded-xl" />
            ))}
          </div>
          <Card className="space-y-4 p-5">
            {Array.from({ length: 6 }, (_, i) => (
              <Skeleton key={i} className="h-9 w-full" />
            ))}
          </Card>
        </div>
      ) : (
        <ParticipantsTable bids={bids} showTenderColumn initialStatus={initialStatus} initialRisk={initialRisk} />
      )}
    </div>
  );
}
