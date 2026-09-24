import { CheckBadge } from "@/components/badges";
import { Card, CardHeader } from "@/components/ui/card";
import type { Criterion } from "@/lib/api";
import { criterionLabel, formatScore, formatValue } from "@/lib/format";
import { cn } from "@/lib/utils";

// Evidence keys worth showing inline; comparison tables get their own card (CrossCheckTable).
const EVIDENCE_LABELS: Record<string, string> = {
  portal_status: "Portal status",
  threshold: "Threshold %",
  declared_pct: "Declared %",
  document_pct: "Certificate %",
  portal_verified_pct: "Portal-verified %",
  declared_employee_count: "Declared employees",
  epfo_registered_employee_count: "EPFO-registered employees",
  portal_category: "Udyam category",
  udyam_status: "Udyam status",
};

type DocRef = { buyer_label?: string | null; document_type: string; why?: string };

export function CriteriaTable({ criteria }: { criteria: Criterion[] }) {
  const mandatory = criteria.filter((c) => c.type === "mandatory");
  const graded = criteria.filter((c) => c.type === "graded");
  const totalWeight = graded.reduce((sum, c) => sum + (c.weight ?? 0), 0);

  return (
    <Card>
      <CardHeader
        title="Criteria breakdown"
        description="Mandatory criteria are pass/fail. Graded criteria are weighted into the overall score."
      />
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-5 py-2 font-medium">Criterion</th>
              <th className="px-3 py-2 font-medium">Result</th>
              <th className="px-3 py-2 text-right font-medium">Weight</th>
              <th className="px-5 py-2 font-medium">Evidence</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            <GroupRow label="Mandatory" />
            {mandatory.map((criterion) => (
              <CriterionRow key={criterion.id} criterion={criterion} totalWeight={totalWeight} />
            ))}
            <GroupRow label="Graded" />
            {graded.map((criterion) => (
              <CriterionRow key={criterion.id} criterion={criterion} totalWeight={totalWeight} />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function GroupRow({ label }: { label: string }) {
  return (
    <tr className="bg-slate-50/60">
      <td colSpan={4} className="px-5 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </td>
    </tr>
  );
}

function CriterionRow({ criterion, totalWeight }: { criterion: Criterion; totalWeight: number }) {
  const failed = criterion.type === "mandatory" ? criterion.passed === false : (criterion.score ?? 100) < 100;
  const evidence = Object.entries(criterion.evidence ?? {}).filter(([key]) => key in EVIDENCE_LABELS);
  const missing = (criterion.evidence?.missing_documents as DocRef[] | undefined) ?? [];
  const notApplicable = (criterion.evidence?.not_applicable_documents as DocRef[] | undefined) ?? [];

  return (
    <tr className={cn(failed && "bg-red-50/40")}>
      <td className="px-5 py-3 align-top">
        <div className="font-medium text-slate-900">{criterionLabel(criterion.id)}</div>
        {criterion.reason && <div className="mt-0.5 text-xs text-slate-600">{criterion.reason}</div>}
      </td>
      <td className="px-3 py-3 align-top">
        {criterion.type === "mandatory" ? <CheckBadge ok={criterion.passed} /> : <ScoreBar score={criterion.score} />}
      </td>
      <td className="px-3 py-3 text-right align-top tabular-nums text-slate-600">
        {criterion.weight && totalWeight ? `${Math.round((criterion.weight / totalWeight) * 100)}%` : "—"}
      </td>
      <td className="px-5 py-3 align-top text-xs text-slate-600">
        {evidence.length > 0 && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
            {evidence.map(([key, value]) => (
              <div key={key} className="contents">
                <dt className="text-slate-500">{EVIDENCE_LABELS[key]}</dt>
                <dd className="font-medium text-slate-800">{formatValue(value)}</dd>
              </div>
            ))}
          </dl>
        )}
        {missing.length > 0 && (
          <ul className="list-disc pl-4 text-red-700">
            {missing.map((doc) => (
              <li key={doc.document_type}>{doc.buyer_label ?? doc.document_type}</li>
            ))}
          </ul>
        )}
        {notApplicable.length > 0 && (
          <ul className="mt-1 space-y-0.5 text-slate-500">
            {notApplicable.map((doc) => (
              <li key={doc.document_type}>
                <span className="font-medium text-slate-700">{doc.buyer_label ?? doc.document_type}</span> — not applicable. {doc.why}
              </li>
            ))}
          </ul>
        )}
        {criterion.id === "declaration_document_consistency" && <span>See cross-verification below.</span>}
        {evidence.length === 0 && missing.length === 0 && notApplicable.length === 0 && criterion.id !== "declaration_document_consistency" && "—"}
      </td>
    </tr>
  );
}

function ScoreBar({ score }: { score: number | null }) {
  if (score === null) return <span className="text-slate-400">—</span>;
  const color = score >= 85 ? "bg-emerald-500" : score >= 60 ? "bg-amber-400" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <span className="h-2 w-20 overflow-hidden rounded-full bg-slate-100" aria-hidden>
        <span className={cn("block h-full", color)} style={{ width: `${Math.max(score, 2)}%` }} />
      </span>
      <span className="text-xs font-semibold tabular-nums text-slate-800">{formatScore(score)}</span>
    </div>
  );
}
