import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const TONES = {
  brand: "bg-brand-50 text-brand-700 ring-brand-100",
  amber: "bg-amber-50 text-amber-700 ring-amber-100",
  red: "bg-red-50 text-red-700 ring-red-100",
  emerald: "bg-emerald-50 text-emerald-700 ring-emerald-100",
  slate: "bg-slate-100 text-slate-700 ring-slate-200",
} as const;

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "brand",
  href,
  loading,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon: LucideIcon;
  tone?: keyof typeof TONES;
  href?: string;
  loading?: boolean;
}) {
  const body = (
    <>
      <div className="flex items-start justify-between gap-3">
        <span className="text-[13px] font-medium text-slate-500">{label}</span>
        <span className={cn("flex h-9 w-9 items-center justify-center rounded-lg ring-1 ring-inset", TONES[tone])}>
          <Icon className="h-[18px] w-[18px]" aria-hidden />
        </span>
      </div>
      {loading ? (
        <>
          <Skeleton className="mt-2 h-8 w-20" />
          <Skeleton className="mt-2 h-3.5 w-28" />
        </>
      ) : (
        <>
          <div className="mt-1 text-[28px] font-semibold leading-9 tracking-tight text-slate-900 tabular-nums">{value}</div>
          {hint && <div className="mt-1 text-[13px] text-slate-500">{hint}</div>}
        </>
      )}
    </>
  );

  const className = "block rounded-xl border border-slate-200/80 bg-white p-5 shadow-card";
  return href ? (
    <a href={href} className={cn(className, "transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-lift")}>
      {body}
    </a>
  ) : (
    <div className={className}>{body}</div>
  );
}
