import { AlertOctagon, Bot, CheckCircle2, CircleHelp, Gavel, XCircle, type LucideIcon } from "lucide-react";
import type { RecentAuditEntry } from "@/lib/api";
import { formatDateTime, formatRelative, formatScore } from "@/lib/format";
import { bidHref } from "@/lib/router";
import { cn } from "@/lib/utils";

function describe(entry: RecentAuditEntry): { icon: LucideIcon; tone: string; title: string; detail: string | null } {
  const payload = entry.payload_json ?? {};
  if (entry.action === "officer_decision") {
    const decision = String(payload.decision ?? "");
    const reason = typeof payload.reason === "string" && payload.reason ? `“${payload.reason}”` : null;
    if (decision === "qualify") return { icon: CheckCircle2, tone: "bg-emerald-50 text-emerald-700 ring-emerald-100", title: "Qualified", detail: reason };
    if (decision === "disqualify") return { icon: XCircle, tone: "bg-red-50 text-red-700 ring-red-100", title: "Disqualified", detail: reason };
    if (decision === "request_clarification")
      return { icon: CircleHelp, tone: "bg-amber-50 text-amber-700 ring-amber-100", title: "Clarification requested", detail: reason };
    return { icon: Gavel, tone: "bg-slate-100 text-slate-600 ring-slate-200", title: "Officer decision", detail: reason };
  }
  if (entry.action === "verify_completed") {
    const score = typeof payload.overall_score === "number" ? formatScore(payload.overall_score) : "—";
    return {
      icon: Bot,
      tone: "bg-brand-50 text-brand-700 ring-brand-100",
      title: "Verification completed",
      detail: `Scored ${score}/100 · ${String(payload.risk_level ?? "—")}`,
    };
  }
  if (entry.action === "verify_failed")
    return { icon: AlertOctagon, tone: "bg-red-50 text-red-700 ring-red-100", title: "Verification failed", detail: String(payload.error ?? "") || null };
  return { icon: Gavel, tone: "bg-slate-100 text-slate-600 ring-slate-200", title: entry.action.replace(/_/g, " "), detail: null };
}

export function ActivityFeed({ entries, dense = false, showBid = true }: { entries: RecentAuditEntry[]; dense?: boolean; showBid?: boolean }) {
  return (
    <ol className="relative">
      {entries.map((entry, i) => {
        const { icon: Icon, tone, title, detail } = describe(entry);
        const who = entry.actor.startsWith("system:") ? "System" : entry.actor;
        return (
          <li key={entry.log_id} className={cn("relative flex gap-3", dense ? "pb-4" : "pb-5", "last:pb-0")}>
            {i < entries.length - 1 && <span className="absolute left-[15px] top-8 h-[calc(100%-1.5rem)] w-px bg-slate-200" aria-hidden />}
            <span className={cn("relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ring-1 ring-inset", tone)}>
              <Icon className="h-4 w-4" aria-hidden />
            </span>
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <p className="text-sm text-slate-900">
                  <span className="font-medium">{title}</span>
                  {showBid && entry.bidder_name && entry.bid_id && (
                    <>
                      {" · "}
                      <a href={bidHref(entry.bid_id)} className="text-slate-700 hover:text-brand-700 hover:underline">
                        {entry.bidder_name}
                      </a>
                    </>
                  )}
                </p>
                <time className="shrink-0 text-xs text-slate-400" dateTime={entry.timestamp} title={formatDateTime(entry.timestamp)}>
                  {formatRelative(entry.timestamp)}
                </time>
              </div>
              {detail && <p className="mt-0.5 line-clamp-2 text-[13px] text-slate-500">{detail}</p>}
              <p className="mt-0.5 text-xs text-slate-400">
                {who}
                {showBid && entry.bid_id && <span className="font-mono"> · {entry.bid_id}</span>}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
