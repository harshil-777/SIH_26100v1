import { Building2, ChevronRight, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { RiskBadge } from "@/components/badges";
import { Card } from "@/components/ui/card";
import { api, type TenderListItem } from "@/lib/api";
import { formatDate, formatInr } from "@/lib/format";
import { tenderHref } from "@/lib/router";

export default function TenderList() {
  const [tenders, setTenders] = useState<TenderListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listTenders().then(setTenders, (cause: Error) => setError(cause.message));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Tenders</h1>
        <p className="mt-1 text-sm text-slate-500">
          {tenders === null && !error ? "Loading…" : `${tenders?.length ?? 0} tenders open for compliance review`}
        </p>
      </div>

      {error && (
        <Card className="border-red-200 bg-red-50 px-5 py-4 text-sm text-red-800">Failed to load tenders: {error}</Card>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {tenders?.map((tender) => (
          <a
            key={tender.tender_id}
            href={tenderHref(tender.tender_id)}
            className="block rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition hover:border-slate-300 hover:shadow"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="truncate font-medium text-slate-900">{tender.title}</div>
                <div className="mt-0.5 flex items-center gap-1 text-xs text-slate-500">
                  <Building2 className="h-3.5 w-3.5 shrink-0" aria-hidden />
                  <span className="truncate">{tender.department}</span>
                </div>
              </div>
              <ChevronRight className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                {tender.category}
              </span>
              {tender.msme_reserved && (
                <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                  MSME reserved
                </span>
              )}
              {tender.worst_risk_level && <RiskBadge risk={tender.worst_risk_level} />}
            </div>

            <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-3 text-xs text-slate-500">
              <span className="font-mono">{tender.tender_id}</span>
              <span>Due {formatDate(tender.submission_deadline)}</span>
            </div>

            <div className="mt-2 flex items-center justify-between text-sm">
              <span className="inline-flex items-center gap-1 font-medium text-slate-800">
                <Users className="h-4 w-4 text-slate-400" aria-hidden />
                {tender.participant_count} participant{tender.participant_count === 1 ? "" : "s"}
              </span>
              <span className="text-slate-500">{formatInr(Number(tender.estimated_value_inr))}</span>
            </div>

            {tender.awaiting_decision_count > 0 && (
              <div className="mt-2 text-xs font-medium text-amber-700">
                {tender.awaiting_decision_count} awaiting an officer decision
              </div>
            )}
          </a>
        ))}
        {tenders !== null && tenders.length === 0 && (
          <Card className="col-span-full px-5 py-10 text-center text-sm text-slate-500">No tenders yet.</Card>
        )}
      </div>
    </div>
  );
}
