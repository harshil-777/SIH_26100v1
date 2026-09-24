import { CheckCircle2, CircleHelp, Loader2, XCircle } from "lucide-react";
import { useState, type FormEvent } from "react";
import { StatusBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { api, type BidStatus, type Decision, type RiskLevel } from "@/lib/api";
import { cn } from "@/lib/utils";

const OFFICER_KEY = "gem.officer";

const OPTIONS: { value: Decision; label: string; icon: typeof CheckCircle2; active: string }[] = [
  { value: "qualify", label: "Qualify", icon: CheckCircle2, active: "border-emerald-600 bg-emerald-50 text-emerald-800" },
  { value: "request_clarification", label: "Request clarification", icon: CircleHelp, active: "border-amber-500 bg-amber-50 text-amber-800" },
  { value: "disqualify", label: "Disqualify", icon: XCircle, active: "border-red-600 bg-red-50 text-red-800" },
];

const SUBMIT_VARIANT = { qualify: "success", request_clarification: "warning", disqualify: "danger" } as const;

function readOfficer(): string {
  try {
    return localStorage.getItem(OFFICER_KEY) ?? "";
  } catch {
    return "";
  }
}

function rememberOfficer(name: string) {
  try {
    localStorage.setItem(OFFICER_KEY, name);
  } catch {
    // Storage blocked (private window etc.) -- the officer just retypes their name next time.
  }
}

export function DecisionPanel({
  bidId,
  status,
  risk,
  onDecided,
}: {
  bidId: string;
  status: BidStatus;
  risk: RiskLevel | null;
  onDecided: () => void;
}) {
  const [decision, setDecision] = useState<Decision | null>(null);
  const [actor, setActor] = useState(readOfficer);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Qualifying against the system's verdict is allowed, but it must be justified on the record.
  const overridesVerdict = decision === "qualify" && (risk === "Non-Compliant" || risk === "High");
  const reasonRequired = decision !== null && (decision !== "qualify" || overridesVerdict);
  const alreadyDecided = status === "qualified" || status === "disqualified" || status === "clarification_requested";

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!decision) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.decide(bidId, { decision, actor: actor.trim(), reason: reason.trim() || null });
      rememberOfficer(actor.trim());
      setDecision(null);
      setReason("");
      onDecided();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Officer decision"
        description="Recorded in the tamper-evident audit log."
        action={<StatusBadge status={status} />}
      />
      <CardBody>
        <form onSubmit={submit} className="space-y-3">
          {alreadyDecided && (
            <p className="text-xs text-slate-500">
              A decision is on record. Recording another one adds a new audit entry; the earlier one is kept.
            </p>
          )}
          <fieldset>
            <legend className="sr-only">Decision</legend>
            <div className="grid gap-2">
              {OPTIONS.map(({ value, label, icon: Icon, active }) => (
                <label
                  key={value}
                  className={cn(
                    "flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition",
                    decision === value ? active : "border-slate-200 text-slate-700 hover:bg-slate-50",
                  )}
                >
                  <input
                    type="radio"
                    name="decision"
                    value={value}
                    checked={decision === value}
                    onChange={() => setDecision(value)}
                    className="sr-only"
                  />
                  <Icon className="h-4 w-4" aria-hidden />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>

          {overridesVerdict && (
            <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              This bid is rated <strong>{risk}</strong>. Qualifying it overrides the system's assessment — record why.
            </p>
          )}

          <label className="block text-xs font-medium text-slate-700">
            Reason{reasonRequired ? " (required)" : " (optional)"}
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              required={reasonRequired}
              rows={3}
              placeholder={decision === "request_clarification" ? "What should the bidder clarify?" : "Basis for this decision"}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-normal focus:border-slate-500 focus:outline-none"
            />
          </label>

          <label className="block text-xs font-medium text-slate-700">
            Officer
            <input
              value={actor}
              onChange={(event) => setActor(event.target.value)}
              required
              placeholder="Name or email"
              autoComplete="email"
              className="mt-1 block h-9 w-full rounded-md border border-slate-300 px-3 text-sm font-normal focus:border-slate-500 focus:outline-none"
            />
          </label>

          {error && <p className="text-xs text-red-700">{error}</p>}

          <Button
            type="submit"
            className="w-full"
            variant={decision ? SUBMIT_VARIANT[decision] : "primary"}
            disabled={!decision || submitting || !actor.trim() || (reasonRequired && !reason.trim())}
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
            {decision ? `Record: ${OPTIONS.find((option) => option.value === decision)!.label}` : "Choose a decision"}
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}
