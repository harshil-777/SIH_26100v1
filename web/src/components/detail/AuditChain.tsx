import { Bot, Link2, Link2Off, ShieldAlert, ShieldCheck, UserRound } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import type { AuditEntry, AuditLog } from "@/lib/api";
import { formatDateTime, formatScore, shortHash, STATUS_LABELS } from "@/lib/format";
import { cn } from "@/lib/utils";

const ACTION_LABELS: Record<string, string> = {
  verify_completed: "Verification completed",
  verify_failed: "Verification failed",
  officer_decision: "Officer decision",
};

export function AuditChain({ log }: { log: AuditLog }) {
  const broken = new Set(log.broken_at);
  // Newest first reads better, but links are checked in chain order (each row vs. the one before it).
  const entries = log.entries.map((entry, index) => ({
    entry,
    linked: index === 0 ? entry.prev_hash === null : entry.prev_hash === log.entries[index - 1].curr_hash,
  }));

  return (
    <Card>
      <CardHeader
        title="Audit trail"
        description="Each entry's hash covers its payload and the previous entry's hash, so any edit breaks the chain."
        action={
          log.chain_valid ? (
            <Badge tone="success">
              <ShieldCheck className="h-3 w-3" aria-hidden />
              Chain intact · {log.entries.length} {log.entries.length === 1 ? "entry" : "entries"}
            </Badge>
          ) : (
            <Badge tone="critical">
              <ShieldAlert className="h-3 w-3" aria-hidden />
              Chain broken
            </Badge>
          )
        }
      />
      {log.entries.length === 0 ? (
        <CardBody className="text-sm text-slate-500">No audit entries yet.</CardBody>
      ) : (
        <ol className="px-5 py-4">
          {[...entries].reverse().map(({ entry, linked }, index) => (
            <AuditRow
              key={entry.log_id}
              entry={entry}
              linked={linked}
              tampered={broken.has(String(entry.log_id))}
              last={index === entries.length - 1}
            />
          ))}
        </ol>
      )}
    </Card>
  );
}

function AuditRow({ entry, linked, tampered, last }: { entry: AuditEntry; linked: boolean; tampered: boolean; last: boolean }) {
  const isSystem = entry.actor.startsWith("system:");
  const Icon = isSystem ? Bot : UserRound;
  const LinkIcon = linked ? Link2 : Link2Off;

  return (
    <li className="relative flex gap-3 pb-5 last:pb-0">
      {!last && <span className="absolute left-[13px] top-7 h-[calc(100%-1.25rem)] w-px bg-slate-200" aria-hidden />}
      <span
        className={cn(
          "relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border",
          tampered ? "border-red-300 bg-red-50 text-red-700" : isSystem ? "border-slate-200 bg-slate-50 text-slate-500" : "border-sky-200 bg-sky-50 text-sky-700",
        )}
      >
        <Icon className="h-3.5 w-3.5" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3">
          <span className="text-sm font-medium text-slate-900">{ACTION_LABELS[entry.action] ?? entry.action}</span>
          <time className="text-xs text-slate-500" dateTime={entry.timestamp}>
            {formatDateTime(entry.timestamp)}
          </time>
        </div>
        <div className="text-xs text-slate-500">
          #{entry.log_id} · {entry.actor}
        </div>
        <PayloadSummary entry={entry} />
        <div
          className={cn(
            "mt-1.5 flex flex-wrap items-center gap-1.5 font-mono text-[11px]",
            tampered ? "text-red-700" : "text-slate-500",
          )}
          title={`prev ${entry.prev_hash ?? "(none)"}\ncurr ${entry.curr_hash}`}
        >
          <LinkIcon className={cn("h-3 w-3", !linked && "text-red-600")} aria-label={linked ? "Linked to previous entry" : "Not linked to previous entry"} />
          <span>{shortHash(entry.prev_hash)}</span>
          <span aria-hidden>→</span>
          <span className="text-slate-700">{shortHash(entry.curr_hash)}</span>
          {tampered && <span className="font-sans font-semibold">hash does not verify</span>}
        </div>
      </div>
    </li>
  );
}

function PayloadSummary({ entry }: { entry: AuditEntry }) {
  const payload = entry.payload_json ?? {};

  if (entry.action === "officer_decision") {
    const newStatus = payload.new_status as keyof typeof STATUS_LABELS | undefined;
    return (
      <p className="mt-1 text-sm text-slate-700">
        <span className="font-medium">{String(payload.decision ?? "").replace(/_/g, " ")}</span>
        {newStatus && STATUS_LABELS[newStatus] && <span className="text-slate-500"> → {STATUS_LABELS[newStatus]}</span>}
        {typeof payload.reason === "string" && payload.reason && <span className="block text-slate-600">“{payload.reason}”</span>}
      </p>
    );
  }
  if (entry.action === "verify_completed") {
    const failures = (payload.mandatory_failure_reasons as string[] | undefined) ?? [];
    return (
      <p className="mt-1 text-sm text-slate-700">
        Score {formatScore(typeof payload.overall_score === "number" ? payload.overall_score : null)} · {String(payload.risk_level ?? "—")}
        {failures.length > 0 && <span className="block text-xs text-red-700">{failures.join(" ")}</span>}
      </p>
    );
  }
  if (typeof payload.error === "string") return <p className="mt-1 text-xs text-red-700">{payload.error}</p>;
  return null;
}
