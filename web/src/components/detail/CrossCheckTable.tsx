import { FileWarning } from "lucide-react";
import { CheckBadge } from "@/components/badges";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import type { Comparison, Criterion } from "@/lib/api";
import { documentTypeLabel, factLabel, formatValue } from "@/lib/format";
import { cn } from "@/lib/utils";

type Leg = "declared" | "document" | "portal";

export function CrossCheckTable({ criterion }: { criterion: Criterion | undefined }) {
  const evidence = criterion?.evidence ?? {};
  const comparisons = Object.entries((evidence.comparisons as Record<string, Comparison> | undefined) ?? {});
  const unreadable = Object.entries((evidence.unreadable_documents as Record<string, string> | undefined) ?? {});
  const superseded = (evidence.superseded_placeholders as string[] | undefined) ?? [];

  return (
    <Card>
      <CardHeader
        title="Cross-verification"
        description="Each fact compared across the bidder's declaration, the uploaded document (OCR) and the government portal."
      />
      {comparisons.length === 0 ? (
        <CardBody className="text-sm text-slate-500">No facts had more than one source to compare for this bid.</CardBody>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-5 py-2 font-medium">Fact</th>
                <th className="px-3 py-2 font-medium">Declared</th>
                <th className="px-3 py-2 font-medium">Document</th>
                <th className="px-3 py-2 font-medium">Portal</th>
                <th className="px-5 py-2 font-medium">Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {comparisons.map(([key, comparison]) => (
                <ComparisonRow key={key} fact={key} comparison={comparison} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(unreadable.length > 0 || superseded.length > 0) && (
        <CardBody className="space-y-2 border-t border-slate-100 text-xs text-slate-600">
          {unreadable.map(([docType, status]) => (
            <p key={docType} className="flex items-start gap-1.5 text-amber-800">
              <FileWarning className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden />
              <span>
                <strong>{documentTypeLabel(docType)}</strong> could not be read ({status}). It is not counted against the
                bidder — check the file manually.
              </span>
            </p>
          ))}
          {superseded.length > 0 && (
            <p>
              Real uploads replaced the seeded placeholder check for:{" "}
              {superseded.map((code) => documentTypeLabel(code)).join(", ")}.
            </p>
          )}
        </CardBody>
      )}
    </Card>
  );
}

function ComparisonRow({ fact, comparison }: { fact: string; comparison: Comparison }) {
  // Seed-fixture placeholders have no per-source values, just a verdict and a note.
  const isPlaceholder = comparison.match === undefined && comparison.document_match !== undefined;
  const ok = isPlaceholder ? comparison.document_match! : comparison.match ?? null;
  const mismatchedLegs = new Set(
    (comparison.mismatched_pairs ?? []).flatMap((pair) => pair.split("_vs_") as Leg[]),
  );

  const cell = (leg: Leg) => {
    const value = comparison[leg];
    const present = value !== null && value !== undefined && value !== "";
    return (
      <td
        className={cn(
          "px-3 py-3 align-top",
          present ? "text-slate-800" : "text-slate-400",
          mismatchedLegs.has(leg) && "font-medium text-red-700",
        )}
      >
        {formatValue(value)}
        {leg === "document" && present && comparison.document_type && (
          <div className="text-[11px] font-normal text-slate-500">{documentTypeLabel(comparison.document_type)}</div>
        )}
      </td>
    );
  };

  return (
    <tr className={cn(ok === false && "bg-red-50/40")}>
      <td className="px-5 py-3 align-top font-medium text-slate-900">{factLabel(fact)}</td>
      {isPlaceholder ? (
        <td colSpan={3} className="px-3 py-3 align-top text-xs text-slate-600">
          {comparison.note ?? "—"}
          <div className="mt-0.5 text-[11px] text-slate-400">Seeded check — no document uploaded yet</div>
        </td>
      ) : (
        <>
          {cell("declared")}
          {cell("document")}
          {cell("portal")}
        </>
      )}
      <td className="px-5 py-3 align-top">
        <CheckBadge ok={ok} label={ok === null ? "N/A" : ok ? "Match" : "Mismatch"} />
        {comparison.note && !isPlaceholder && <div className="mt-1 text-xs text-slate-500">{comparison.note}</div>}
      </td>
    </tr>
  );
}
