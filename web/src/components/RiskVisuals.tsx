import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { RISK_KEYS, RISK_STYLE, type RiskKey } from "@/lib/risk";
import { cn } from "@/lib/utils";

type Counts = Record<RiskKey, number>;

// One thin stacked bar showing how a group of bids splits across risk levels.
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

export function RiskLegend({ counts, onSelect, selected }: { counts: Counts; onSelect?: (key: RiskKey) => void; selected?: RiskKey | null }) {
  const total = RISK_KEYS.reduce((sum, key) => sum + counts[key], 0);
  return (
    <ul className="space-y-1">
      {RISK_KEYS.map((key) => {
        const pct = total ? Math.round((counts[key] / total) * 100) : 0;
        const content = (
          <>
            <span className={cn("h-2.5 w-2.5 shrink-0 rounded-sm", RISK_STYLE[key].dot)} aria-hidden />
            <span className="flex-1 text-slate-600">{RISK_STYLE[key].label}</span>
            <span className="font-semibold tabular-nums text-slate-900">{counts[key]}</span>
            <span className="w-9 text-right text-xs tabular-nums text-slate-400">{pct}%</span>
          </>
        );
        return (
          <li key={key}>
            {onSelect ? (
              <button
                type="button"
                onClick={() => onSelect(key)}
                aria-pressed={selected === key}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-sm transition hover:bg-slate-50",
                  selected === key && "bg-slate-100",
                )}
              >
                {content}
              </button>
            ) : (
              <div className="flex items-center gap-2.5 px-2 py-1.5 text-sm">{content}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export function RiskDonut({ counts, centerLabel }: { counts: Counts; centerLabel: string }) {
  const total = RISK_KEYS.reduce((sum, key) => sum + counts[key], 0);
  const data = RISK_KEYS.filter((key) => counts[key] > 0).map((key) => ({ key, name: RISK_STYLE[key].label, value: counts[key] }));
  return (
    <div className="relative mx-auto h-44 w-44">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data.length ? data : [{ key: "unverified", name: "None", value: 1 }]}
            dataKey="value"
            innerRadius="70%"
            outerRadius="100%"
            paddingAngle={data.length > 1 ? 2 : 0}
            stroke="none"
            isAnimationActive={false}
          >
            {(data.length ? data : [{ key: "unverified" as RiskKey }]).map((entry) => (
              <Cell key={entry.key} fill={data.length ? RISK_STYLE[entry.key].hex : "#e2e8f0"} />
            ))}
          </Pie>
          {data.length > 0 && (
            <Tooltip
              formatter={(value: number, name: string) => [`${value} bid${value === 1 ? "" : "s"}`, name]}
              contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 12, boxShadow: "0 8px 20px -6px rgb(16 24 40 / .15)" }}
            />
          )}
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-semibold tabular-nums tracking-tight text-slate-900">{total}</span>
        <span className="text-xs text-slate-500">{centerLabel}</span>
      </div>
    </div>
  );
}
