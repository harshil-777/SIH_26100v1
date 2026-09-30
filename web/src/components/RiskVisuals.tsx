import { RISK_KEYS, RISK_STYLE, type RiskKey } from "@/lib/risk";
import { cn } from "@/lib/utils";

type Counts = Record<RiskKey, number>;

// One stacked bar showing how a group of bids splits across risk levels.
export function RiskBar({ counts, className }: { counts: Counts; className?: string }) {
  const total = RISK_KEYS.reduce((sum, key) => sum + counts[key], 0);
  if (total === 0) return <div className={cn("h-2 rounded-full bg-slate-100", className)} aria-label="No bids" />;
  const summary = RISK_KEYS.filter((key) => counts[key] > 0)
    .map((key) => `${counts[key]} ${RISK_STYLE[key].label.toLowerCase()}`)
    .join(", ");
  return (
    <div className={cn("flex h-2 gap-0.5 overflow-hidden rounded-full", className)} role="img" aria-label={summary} title={summary}>
      {RISK_KEYS.filter((key) => counts[key] > 0).map((key) => (
        <span key={key} className={RISK_STYLE[key].dot} style={{ width: `${(counts[key] / total) * 100}%` }} />
      ))}
    </div>
  );
}

// Colour key for a set of RiskBars.
export function RiskKeyLegend() {
  return (
    <ul className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
      {RISK_KEYS.map((key) => (
        <li key={key} className="inline-flex items-center gap-1.5">
          <span className={cn("h-2 w-2 rounded-sm", RISK_STYLE[key].dot)} aria-hidden />
          {RISK_STYLE[key].label}
        </li>
      ))}
    </ul>
  );
}
