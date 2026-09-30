import { Loader2, RefreshCw, ShieldAlert, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, type AuditVerification } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { bidHref } from "@/lib/router";
import { cn } from "@/lib/utils";

// Whole-log integrity check: the server recomputes every bid's hash chain on each request.
export function AuditIntegrity({ onResult }: { onResult?: (result: AuditVerification) => void } = {}) {
  const [result, setResult] = useState<AuditVerification | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  const check = useCallback(async () => {
    setChecking(true);
    setError(null);
    try {
      const verification = await api.verifyAuditLog();
      setResult(verification);
      onResult?.(verification);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setChecking(false);
    }
  }, [onResult]);

  useEffect(() => {
    check();
  }, [check]);

  const broken = Boolean(result && !result.valid);
  const bad = broken || Boolean(error);
  const Icon = bad ? ShieldAlert : ShieldCheck;

  return (
    <Card className={cn("overflow-hidden", broken && "border-red-300")}>
      <div className={cn("flex flex-wrap items-center gap-4 px-5 py-4", broken ? "bg-red-50" : "bg-gradient-to-r from-emerald-50/70 to-white")}>
        <span
          className={cn(
            "flex h-11 w-11 shrink-0 items-center justify-center rounded-full ring-1 ring-inset",
            !result && !error ? "bg-slate-100 text-slate-500 ring-slate-200" : bad ? "bg-red-100 text-red-700 ring-red-200" : "bg-emerald-100 text-emerald-700 ring-emerald-200",
          )}
        >
          {!result && !error ? <Loader2 className="h-5 w-5 animate-spin" aria-hidden /> : <Icon className="h-5 w-5" aria-hidden />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-[15px] font-semibold text-slate-900">
            {error
              ? "Audit log could not be checked"
              : !result
                ? "Checking audit log integrity…"
                : result.valid
                  ? "Audit log intact — no tampering detected"
                  : `Tampering detected — ${result.breaks.length} broken ${result.breaks.length === 1 ? "link" : "links"}`}
          </div>
          <div className="mt-0.5 text-[13px] text-slate-500">
            {error
              ? error
              : result
                ? `Recomputed ${result.entries_checked} hash-chained entries across ${result.chains_checked} bids · checked ${formatDateTime(result.checked_at)}`
                : "Recomputing every bid's SHA-256 hash chain on the server."}
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={check} disabled={checking}>
          {checking ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : <RefreshCw className="h-3.5 w-3.5" aria-hidden />}
          Re-check
        </Button>
      </div>
      {broken && result && (
        <ul className="border-t border-red-200 px-5 py-3 text-[13px] text-red-800">
          {result.breaks.map((found) => (
            <li key={`${found.bid_id}-${found.log_id}-${found.problem}`} className="py-0.5">
              {found.bid_id ? (
                <a href={bidHref(found.bid_id)} className="font-mono underline">
                  {found.bid_id}
                </a>
              ) : (
                <span className="font-mono">(no bid)</span>
              )}{" "}
              entry #{found.log_id}: {found.problem}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
