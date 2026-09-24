import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { toNumber, type BidDetail } from "@/lib/api";
import { formatDate, formatInr, formatValue } from "@/lib/format";

export function BidderProfile({ bid }: { bid: BidDetail }) {
  const { bidder, tender } = bid;
  const threshold = toNumber(tender.mii_local_content_threshold_pct);

  const identifiers: [string, string | number | null][] = [
    ["PAN", bidder.pan],
    ["GSTIN", bidder.gstin],
    ["Udyam", bidder.udyam_number],
    ["CIN", bidder.cin],
    ["DPIIT", bidder.dpiit_recognition_number],
    ["NSIC", bidder.nsic_registration_number],
    ["EPFO code", bidder.epfo_establishment_code],
    ["Employees", bidder.employee_count],
  ];
  const conditions = [
    tender.msme_reserved && "Reserved for MSMEs",
    threshold !== null && threshold > 0 && `Make in India: ≥${threshold}% local content`,
    tender.requires_oem_authorization && "OEM authorization required",
  ].filter(Boolean) as string[];

  return (
    <Card>
      <CardHeader title="Bidder & tender" />
      <CardBody className="space-y-4 text-sm">
        <div>
          <div className="font-medium text-slate-900">{bidder.name}</div>
          <div className="text-xs text-slate-500">
            {bidder.bidder_id} · {bidder.enterprise_category ?? "—"} enterprise · {bidder.state ?? "—"}
          </div>
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
            {identifiers
              .filter(([, value]) => value !== null && value !== "")
              .map(([label, value]) => (
                <div key={label} className="contents">
                  <dt className="text-slate-500">{label}</dt>
                  <dd className="break-all font-mono text-slate-800">{formatValue(value)}</dd>
                </div>
              ))}
          </dl>
        </div>

        <div className="border-t border-slate-100 pt-3">
          <div className="font-medium text-slate-900">{tender.title}</div>
          <div className="text-xs text-slate-500">
            {tender.tender_id} · {tender.department} · {tender.category}
          </div>
          <div className="mt-1 text-xs text-slate-600">
            Est. value {formatInr(toNumber(tender.estimated_value_inr) ?? 0)} · Deadline {formatDate(tender.submission_deadline)}
          </div>
          {conditions.length > 0 && (
            <ul className="mt-1.5 list-disc pl-4 text-xs text-slate-600">
              {conditions.map((condition) => (
                <li key={condition}>{condition}</li>
              ))}
            </ul>
          )}
        </div>

        {bid.declarations.length > 0 && (
          <div className="border-t border-slate-100 pt-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Self-declarations</div>
            <dl className="mt-1.5 space-y-1 text-xs">
              {bid.declarations.map((declaration) => (
                <div key={declaration.declaration_id} className="flex justify-between gap-3">
                  <dt className="text-slate-500">{declaration.criterion_code.replace(/_self_declared$/, "").replace(/_/g, " ")}</dt>
                  <dd className="text-right font-medium text-slate-800">{declaration.declared_value}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
