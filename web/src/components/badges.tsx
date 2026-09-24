import { AlertOctagon, CheckCircle2, CircleHelp, Clock, ShieldAlert, ShieldCheck, XCircle } from "lucide-react";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import type { BidStatus, RiskLevel } from "@/lib/api";
import { STATUS_LABELS } from "@/lib/format";

export const RISK_TONE: Record<RiskLevel, BadgeTone> = {
  Low: "success",
  Medium: "warning",
  High: "danger",
  "Non-Compliant": "critical",
};

export function RiskBadge({ risk }: { risk: RiskLevel | null }) {
  if (!risk) return <Badge tone="neutral">Not verified</Badge>;
  const Icon = risk === "Low" ? ShieldCheck : risk === "Non-Compliant" ? AlertOctagon : ShieldAlert;
  return (
    <Badge tone={RISK_TONE[risk]}>
      <Icon className="h-3 w-3" aria-hidden />
      {risk}
    </Badge>
  );
}

const STATUS_TONE: Record<BidStatus, BadgeTone> = {
  submitted: "neutral",
  under_review: "info",
  qualified: "success",
  disqualified: "danger",
  clarification_requested: "warning",
};

export function StatusBadge({ status }: { status: BidStatus }) {
  const Icon =
    status === "qualified" ? CheckCircle2 : status === "disqualified" ? XCircle : status === "clarification_requested" ? CircleHelp : Clock;
  return (
    <Badge tone={STATUS_TONE[status]}>
      <Icon className="h-3 w-3" aria-hidden />
      {STATUS_LABELS[status]}
    </Badge>
  );
}

// pass / fail / partial for a single check. `null` means "not applicable / not checked".
export function CheckBadge({ ok, label }: { ok: boolean | null; label?: string }) {
  if (ok === null) return <Badge tone="neutral">{label ?? "N/A"}</Badge>;
  return ok ? (
    <Badge tone="success">
      <CheckCircle2 className="h-3 w-3" aria-hidden />
      {label ?? "Pass"}
    </Badge>
  ) : (
    <Badge tone="danger">
      <XCircle className="h-3 w-3" aria-hidden />
      {label ?? "Fail"}
    </Badge>
  );
}
