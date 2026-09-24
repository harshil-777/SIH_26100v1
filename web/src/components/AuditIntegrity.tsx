import { Loader2, RefreshCw, ShieldAlert, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, type AuditVerification } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { bidHref } from "@/lib/router";

// Whole-log integrity check: the server recomputes every bid's hash chain on each request.
export function AuditIntegrity() {
  const [result, setResult] = useState<AuditVerification | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  const check = useCallback(async () => {
    setChecking(true);
    setError(null);
    try {
      setResult(await api.verifyAuditLog());
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    check();
  }, [check]);

  const broken = result && !result.valid;
  const Icon = broken || error ? ShieldAlert : ShieldCheck;

  return (
    <Card className={broken ? "border-red-300 bg-red-50" : undefined}>
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <Icon className={`h-5 w-5 shrink-0 ${broken || error ? "text-red-700" : "text-emerald-700"}`} aria-hidden />
        <div className="min-w-0 flex-1 text-sm">
          <div className="font-medium text-slate-900">
            {error
              ? "Audit log could not be checked"
              : !result
                ? "Checking audit log integrity…"
                : result.valid
                  ? "Audit log intact"
                  : `Audit log tampering detected — ${result.breaks.length} broken ${result.breaks.length === 1 ? "link" : "links"}`}
          </div>
          <div className="text-xs text-slate-500">
            {error
              ? error
              : result &&
                `Recomputed ${result.entries_checked} hash-chained entries across ${result.chains_checked} bids · checked ${formatDateTime(result.checked_at)}`}
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={check} disabled={checking}>
          {checking ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : <RefreshCw className="h-3.5 w-3.5" aria-hidden />}
          Re-check
        </Button>
      </div>
      {broken && (
        <ul className="border-t border-red-200 px-4 py-2 text-xs text-red-800">
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
