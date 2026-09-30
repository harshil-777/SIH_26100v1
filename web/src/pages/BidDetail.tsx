import { AlertTriangle, CalendarDays, Loader2, MapPin, PlayCircle, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { RiskBadge, StatusBadge } from "@/components/badges";
import { Breadcrumbs } from "@/components/PageHeader";
import { ErrorState } from "@/components/States";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime, formatScore, initials } from "@/lib/format";
import { RISK_STYLE } from "@/lib/risk";
import { overviewHref, tenderHref, tendersHref } from "@/lib/router";
import { AuditChain } from "@/components/detail/AuditChain";
import { BidderProfile } from "@/components/detail/BidderProfile";
import { CriteriaTable } from "@/components/detail/CriteriaTable";
import { CrossCheckTable } from "@/components/detail/CrossCheckTable";
import { DecisionPanel } from "@/components/detail/DecisionPanel";
import { DocumentsPanel } from "@/components/detail/DocumentsPanel";
import { PortalChecks } from "@/components/detail/PortalChecks";
import { ScoreSummary } from "@/components/detail/ScoreSummary";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { api, ApiError, toNumber, type AuditLog, type BidDetail as Bid, type BidDocument, type ComplianceScore } from "@/lib/api";

type Data = { bid: Bid; score: ComplianceScore | null; documents: BidDocument[]; audit: AuditLog };

const POLL_MS = 2000;
const POLL_LIMIT = 90; // ~3 minutes; the pipeline normally takes seconds.
const MAX_FAILED_POLLS = 3;

export default function BidDetail({ bidId }: { bidId: string }) {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const cancelled = useRef(false);

  const load = useCallback(async () => {
    try {
      const [bid, score, documents, audit] = await Promise.all([
        api.getBid(bidId),
        api.getScore(bidId),
        api.getDocuments(bidId),
        api.getAuditLog(bidId),
      ]);
      if (!cancelled.current) {
        setData({ bid, score, documents, audit });
        setError(null);
      }
    } catch (cause) {
      if (!cancelled.current) setError({ status: cause instanceof ApiError ? cause.status : 0, message: (cause as Error).message });
    }
  }, [bidId]);

  useEffect(() => {
    cancelled.current = false;
    setData(null);
    load();
    return () => {
      cancelled.current = true;
    };
  }, [load]);

  async function runVerification() {
    setVerifying(true);
    setVerifyError(null);
    try {
      const started = await api.verify(bidId);
      // sync_pipeline deployments (e.g. Cloud Run, where a background worker can't rely on
      // getting CPU between requests) run the pipeline inline and answer with the final
      // status already -- nothing to poll for. Celery deployments answer "queued" and the
      // loop below waits on GET /status as before.
      if (started.status === "failed") throw new Error(started.error ?? "Verification failed");
      if (started.status === "success") {
        await load();
        return;
      }
      let failedPolls = 0;
      for (let attempt = 0; attempt < POLL_LIMIT && !cancelled.current; attempt++) {
        await new Promise((resolve) => setTimeout(resolve, POLL_MS));
        let job;
        try {
          job = await api.getJobStatus(bidId);
          failedPolls = 0;
        } catch (cause) {
          // The job keeps running server-side; one dropped status request shouldn't end the wait.
          if (++failedPolls >= MAX_FAILED_POLLS) throw cause;
          continue;
        }
        if (job.job_status === "success") break;
        if (job.job_status === "failed") throw new Error(job.error ?? "Verification failed");
        if (attempt === POLL_LIMIT - 1) throw new Error("Verification is taking unusually long — check the worker.");
      }
      await load();
    } catch (cause) {
      setVerifyError((cause as Error).message);
    } finally {
      if (!cancelled.current) setVerifying(false);
    }
  }

  if (error) {
    return (
      <div className="page-enter space-y-5">
        <Breadcrumbs crumbs={[{ label: "Overview", href: overviewHref }, { label: "Tenders", href: tendersHref }, { label: bidId }]} />
        <ErrorState
          title={error.status === 404 ? "Bid not found" : "Couldn't load this bid"}
          message={error.status === 404 ? `There is no bid with ID ${bidId}.` : error.message}
          onRetry={error.status === 404 ? undefined : load}
        />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-4 w-64" />
        <Card className="flex items-center gap-5 p-6">
          <Skeleton className="h-16 w-16 rounded-2xl" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-7 w-1/3" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        </Card>
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
          <Skeleton className="h-80 rounded-xl" />
          <Skeleton className="h-80 rounded-xl" />
        </div>
      </div>
    );
  }

  const { bid, score, documents, audit } = data;
  const criteria = score?.criterion_breakdown_json.criteria ?? [];
  const consistency = criteria.find((c) => c.id === "declaration_document_consistency");
  const notApplicableDocs = (
    (criteria.find((c) => c.id === "document_completeness")?.evidence.not_applicable_documents as { document_type: string }[] | undefined) ?? []
  ).map((doc) => doc.document_type);

  const overall = score ? toNumber(score.overall_score) : null;

  return (
    <div className="page-enter space-y-5">
      <Breadcrumbs
        crumbs={[
          { label: "Overview", href: overviewHref },
          { label: "Tenders", href: tendersHref },
          { label: bid.tender.tender_id, href: tenderHref(bid.tender.tender_id) },
          { label: bid.bid_id },
        ]}
      />

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-5 p-5 sm:p-6">
          <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 text-xl font-semibold text-white shadow-sm">
            {initials(bid.bidder.name)}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{bid.bidder.name}</h1>
              <RiskBadge risk={score?.risk_level ?? null} />
              <StatusBadge status={bid.status} />
            </div>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-slate-500">
              <span className="font-mono">{bid.bid_id}</span>
              <a href={tenderHref(bid.tender.tender_id)} className="max-w-[22rem] truncate hover:text-brand-700 hover:underline">
                {bid.tender.title}
              </a>
              <span className="inline-flex items-center gap-1">
                <CalendarDays className="h-3.5 w-3.5" aria-hidden /> Submitted {formatDateTime(bid.submitted_at)}
              </span>
              {bid.bidder.state && (
                <span className="inline-flex items-center gap-1">
                  <MapPin className="h-3.5 w-3.5" aria-hidden /> {bid.bidder.state}
                </span>
              )}
            </div>
          </div>

          <div className="flex w-full items-center gap-5 sm:w-auto">
            {overall !== null && score && (
              <div className="border-slate-200 text-right sm:border-l sm:pl-5">
                <div className="text-xs font-medium text-slate-500">Compliance score</div>
                <div className="text-3xl font-semibold tabular-nums tracking-tight" style={{ color: RISK_STYLE[score.risk_level].hex }}>
                  {formatScore(overall)}
                  <span className="text-base font-medium text-slate-400">/100</span>
                </div>
              </div>
            )}
            <Button onClick={runVerification} disabled={verifying} variant={score ? "outline" : "primary"} className="ml-auto sm:ml-0">
              {verifying ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              ) : score ? (
                <RefreshCw className="h-4 w-4" aria-hidden />
              ) : (
                <PlayCircle className="h-4 w-4" aria-hidden />
              )}
              {verifying ? "Verifying…" : score ? "Re-run verification" : "Run verification"}
            </Button>
          </div>
        </div>

        {verifying && <VerifyingStrip />}
        {verifyError && !verifying && (
          <div className="flex items-start gap-2 border-t border-red-200 bg-red-50 px-6 py-3 text-sm text-red-800">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <span>
              <strong className="font-semibold">Verification failed.</strong> {verifyError}
            </span>
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          {score ? (
            <>
              <ScoreSummary score={score} />
              <CriteriaTable criteria={score.criterion_breakdown_json.criteria} />
              <CrossCheckTable criterion={consistency} />
            </>
          ) : (
            <Card>
              <CardBody className="flex flex-col items-center py-10 text-center">
                <span className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-100">
                  <PlayCircle className="h-6 w-6" aria-hidden />
                </span>
                <h2 className="mt-4 text-base font-semibold text-slate-900">Not verified yet</h2>
                <p className="mt-1 max-w-md text-sm text-slate-500">
                  Run verification to check this bid against the tender's eligibility rules, the uploaded documents and the
                  government registries, and get a compliance score.
                </p>
                <Button className="mt-5" onClick={runVerification} disabled={verifying}>
                  {verifying ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <PlayCircle className="h-4 w-4" aria-hidden />}
                  Run verification
                </Button>
              </CardBody>
            </Card>
          )}
          <DocumentsPanel documents={documents} notApplicable={notApplicableDocs} />
          <PortalChecks results={bid.verification_results} />
        </div>

        <div className="space-y-5">
          <DecisionPanel bidId={bid.bid_id} status={bid.status} risk={score?.risk_level ?? null} onDecided={load} />
          <BidderProfile bid={bid} />
          <AuditChain log={audit} />
        </div>
      </div>
    </div>
  );
}

// Real elapsed time rather than fake stage-by-stage progress: the API runs the pipeline in one
// request and reports nothing until it finishes.
function VerifyingStrip() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 500);
    return () => window.clearInterval(timer);
  }, []);
  return (
    <div className="border-t border-brand-100 bg-brand-50/70 px-6 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="flex items-center gap-2 font-medium text-brand-900">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Running the compliance pipeline — registry checks, document extraction, rule engine, scoring and AI review
        </span>
        <span className="tabular-nums text-brand-700">{seconds}s</span>
      </div>
      <div className="mt-2 h-1 overflow-hidden rounded-full bg-brand-100">
        <div className="h-full w-1/3 animate-verify-slide rounded-full bg-brand-500" />
      </div>
      {seconds >= 15 && (
        <p className="mt-2 text-xs text-brand-800">
          Taking a little longer — the first run after the server wakes up also loads the AI models.
        </p>
      )}
    </div>
  );
}
