import { ArrowLeft, Building2 } from "lucide-react";
import { useEffect, useState } from "react";
import { AuditIntegrity } from "@/components/AuditIntegrity";
import { ParticipantsTable } from "@/components/ParticipantsTable";
import { Card } from "@/components/ui/card";
import { api, ApiError, type DashboardBid, type TenderOut } from "@/lib/api";
import { formatDate, formatInr } from "@/lib/format";

type Data = { tender: TenderOut; bids: DashboardBid[] };

export default function TenderDetail({ tenderId }: { tenderId: string }) {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    Promise.all([api.getTender(tenderId), api.listBids(tenderId)])
      .then(([tender, bids]) => {
        if (!cancelled) setData({ tender, bids });
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError({ status: cause instanceof ApiError ? cause.status : 0, message: (cause as Error).message });
      });
    return () => {
      cancelled = true;
    };
  }, [tenderId]);

  if (error) {
    return (
      <div className="space-y-4">
        <BackLink />
        <Card className="border-red-200 bg-red-50 px-5 py-4 text-sm text-red-800">
          {error.status === 404 ? `Tender ${tenderId} not found.` : `Failed to load tender: ${error.message}`}
        </Card>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="space-y-4">
        <BackLink />
        <p className="text-sm text-slate-500">Loading…</p>
      </div>
    );
  }

  const { tender, bids } = data;
  const awaitingDecision = bids.filter((bid) => bid.status === "submitted" || bid.status === "under_review").length;

  return (
    <div className="space-y-6">
      <BackLink />

      <Card className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">{tender.title}</h1>
            <div className="mt-1 flex items-center gap-1.5 text-sm text-slate-500">
              <Building2 className="h-4 w-4" aria-hidden />
              {tender.department}
            </div>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">{tender.category}</span>
            {tender.msme_reserved && (
              <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
                MSME reserved
              </span>
            )}
            {tender.requires_oem_authorization && (
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
                OEM authorization required
              </span>
            )}
          </div>
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-4 border-t border-slate-100 pt-4 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-xs text-slate-500">Tender ID</dt>
            <dd className="font-mono text-slate-800">{tender.tender_id}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Estimated value</dt>
            <dd className="text-slate-800">{formatInr(Number(tender.estimated_value_inr))}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Submission deadline</dt>
            <dd className="text-slate-800">{formatDate(tender.submission_deadline)}</dd>
          </div>
          {tender.mii_local_content_threshold_pct !== null && (
            <div>
              <dt className="text-xs text-slate-500">Min. local content</dt>
              <dd className="text-slate-800">{Number(tender.mii_local_content_threshold_pct)}%</dd>
            </div>
          )}
        </dl>
      </Card>

      <AuditIntegrity />

      <div>
        <h2 className="text-sm font-semibold text-slate-900">
          Participants <span className="font-normal text-slate-500">({bids.length})</span>
        </h2>
        {awaitingDecision > 0 && (
          <p className="mt-0.5 text-xs text-amber-700">{awaitingDecision} awaiting an officer decision</p>
        )}
      </div>
      <ParticipantsTable bids={bids} />
    </div>
  );
}

function BackLink() {
  return (
    <a href="#/" className="inline-flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900">
      <ArrowLeft className="h-4 w-4" aria-hidden />
      All tenders
    </a>
  );
}
