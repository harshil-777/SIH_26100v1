import { ArrowLeft, Loader2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { RiskBadge } from "@/components/badges";
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
import { api, ApiError, type AuditLog, type BidDetail as Bid, type BidDocument, type ComplianceScore } from "@/lib/api";

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
      await api.verify(bidId);
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
      <div className="space-y-4">
        <BackLink />
        <Card className="border-red-200 bg-red-50">
          <CardBody className="text-sm text-red-800">
            {error.status === 404 ? `Bid ${bidId} was not found.` : `Failed to load this bid: ${error.message}`}
          </CardBody>
        </Card>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="space-y-4">
        <BackLink />
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Loading bid…
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

  return (
    <div className="space-y-5">
      <BackLink />

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold text-slate-900">{bid.bidder.name}</h1>
            <RiskBadge risk={score?.risk_level ?? null} />
          </div>
          <p className="mt-1 text-sm text-slate-500">
            <span className="font-mono">{bid.bid_id}</span> · {bid.tender.title}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Button variant="outline" onClick={runVerification} disabled={verifying}>
            {verifying ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <RefreshCw className="h-4 w-4" aria-hidden />}
            {verifying ? "Verifying…" : score ? "Re-run verification" : "Run verification"}
          </Button>
          {verifyError && <p className="max-w-xs text-right text-xs text-red-700">{verifyError}</p>}
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-5">
          {score ? (
            <>
              <ScoreSummary score={score} />
              <CriteriaTable criteria={score.criterion_breakdown_json.criteria} />
              <CrossCheckTable criterion={consistency} />
            </>
          ) : (
            <Card>
              <CardBody className="text-sm text-slate-600">
                This bid hasn't been verified yet. Run verification to check it against the government portals and score it.
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

function BackLink() {
  return (
    <a href="#/" className="inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900">
      <ArrowLeft className="h-4 w-4" aria-hidden /> All bids
    </a>
  );
}
