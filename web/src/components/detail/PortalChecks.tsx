import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { toNumber, type BidDetail } from "@/lib/api";
import { formatValue, sourceLabel } from "@/lib/format";

// Statuses an adapter returns when all is well; anything in BAD is a red flag. not_found is only
// a caution (Udyam often answers it for bidders a category doesn't require); everything else
// (reported, not_checked, ...) is informational.
const GOOD = new Set(["active", "valid", "clear", "verified", "recognized", "registered"]);
const BAD = new Set(["cancelled", "invalid", "debarred", "suspended", "expired", "inactive", "struck_off", "mismatch"]);
const CAUTION = new Set(["not_found"]);

// Bookkeeping keys already shown elsewhere on the card.
const HIDDEN_KEYS = new Set(["status", "confidence", "verified_at"]);

function statusTone(status: string): BadgeTone {
  const normalized = status.toLowerCase();
  if (GOOD.has(normalized)) return "success";
  if (BAD.has(normalized)) return "danger";
  if (CAUTION.has(normalized)) return "warning";
  return "neutral";
}

export function PortalChecks({ results }: { results: BidDetail["verification_results"] }) {
  return (
    <Card>
      <CardHeader title="Government portal checks" description="Latest response from each verification source." />
      {results.length === 0 ? (
        <CardBody className="text-sm text-slate-500">No portal checks yet — run verification.</CardBody>
      ) : (
        <div className="grid gap-px bg-slate-100 sm:grid-cols-2">
          {results.map((result) => {
            const confidence = toNumber(result.confidence_score);
            const details = Object.entries(result.raw_response_json ?? {}).filter(([key]) => !HIDDEN_KEYS.has(key));
            return (
              <div key={result.source} className="bg-white px-5 py-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-slate-900">{sourceLabel(result.source)}</span>
                  <Badge tone={statusTone(result.status)}>{result.status.replace(/_/g, " ")}</Badge>
                </div>
                {confidence !== null && (
                  <div className="mt-0.5 text-[11px] text-slate-500">Confidence {Math.round(confidence * 100)}%</div>
                )}
                {details.length > 0 && (
                  <dl className="mt-2 space-y-0.5 text-xs">
                    {details.map(([key, value]) => (
                      <div key={key} className="flex gap-2">
                        <dt className="shrink-0 text-slate-500">{key.replace(/_/g, " ")}</dt>
                        <dd className="min-w-0 break-words font-medium text-slate-800">{formatValue(value)}</dd>
                      </div>
                    ))}
                  </dl>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
