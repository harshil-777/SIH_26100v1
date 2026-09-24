import { AlertOctagon, Sparkles } from "lucide-react";
import { PolarAngleAxis, RadialBar, RadialBarChart, ResponsiveContainer } from "recharts";
import { RiskBadge } from "@/components/badges";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { toNumber, type ComplianceScore } from "@/lib/api";
import { formatDateTime, formatScore } from "@/lib/format";

const RISK_COLOR: Record<string, string> = {
  Low: "#059669",
  Medium: "#d97706",
  High: "#dc2626",
  "Non-Compliant": "#991b1b",
};

const ADVISORY_PREFIX = "AI-generated, advisory only: ";

export function ScoreSummary({ score }: { score: ComplianceScore }) {
  const overall = toNumber(score.overall_score) ?? 0;
  const failures = score.criterion_breakdown_json.mandatory_failure_reasons;
  const advisory = score.recommendation.startsWith(ADVISORY_PREFIX)
    ? score.recommendation.slice(ADVISORY_PREFIX.length)
    : score.recommendation;

  return (
    <Card>
      <CardHeader title="Compliance score" description={`Last verified ${formatDateTime(score.generated_at)}`} />
      <CardBody className="grid gap-6 md:grid-cols-[190px_1fr]">
        <div className="relative mx-auto h-[180px] w-[180px]">
          <ResponsiveContainer width="100%" height="100%">
            <RadialBarChart
              data={[{ value: overall }]}
              innerRadius="78%"
              outerRadius="100%"
              startAngle={225}
              endAngle={-45}
              barSize={14}
            >
              <PolarAngleAxis type="number" domain={[0, 100]} tick={false} axisLine={false} />
              <RadialBar
                dataKey="value"
                cornerRadius={7}
                fill={RISK_COLOR[score.risk_level]}
                background={{ fill: "#f1f5f9" }}
                isAnimationActive={false}
              />
            </RadialBarChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-semibold tabular-nums text-slate-900">{formatScore(overall)}</span>
            <span className="text-xs text-slate-500">out of 100</span>
            <span className="mt-1.5">
              <RiskBadge risk={score.risk_level} />
            </span>
          </div>
        </div>

        <div className="space-y-4">
          {failures.length > 0 && (
            <div className="rounded-md border border-red-200 bg-red-50 p-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-red-800">
                <AlertOctagon className="h-4 w-4" aria-hidden />
                {failures.length === 1 ? "1 mandatory criterion failed" : `${failures.length} mandatory criteria failed`}
              </div>
              <ul className="mt-1.5 list-disc space-y-0.5 pl-6 text-sm text-red-800">
                {failures.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-red-700">A mandatory failure caps the score at 40 and marks the bid Non-Compliant.</p>
            </div>
          )}

          <div className="rounded-md border border-violet-200 bg-violet-50/60 p-3">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-violet-700" aria-hidden />
              <span className="text-sm font-semibold text-violet-900">Recommendation</span>
              <span className="rounded bg-violet-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-800">
                AI-generated · advisory only
              </span>
            </div>
            <p className="mt-1.5 text-sm text-slate-700">{advisory}</p>
            <p className="mt-1.5 text-xs text-slate-500">
              Not a decision. The procurement officer makes and records the final call below.
            </p>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
