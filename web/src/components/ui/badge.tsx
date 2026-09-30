import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
  {
    variants: {
      tone: {
        neutral: "bg-slate-50 text-slate-700 ring-slate-200",
        success: "bg-emerald-50 text-emerald-800 ring-emerald-200",
        warning: "bg-amber-50 text-amber-800 ring-amber-200",
        orange: "bg-orange-50 text-orange-800 ring-orange-200",
        danger: "bg-red-50 text-red-800 ring-red-200",
        critical: "bg-red-700 text-white ring-red-700",
        info: "bg-sky-50 text-sky-800 ring-sky-200",
        brand: "bg-brand-50 text-brand-800 ring-brand-200",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export type BadgeTone = NonNullable<VariantProps<typeof badgeVariants>["tone"]>;

export function Badge({ className, tone, ...props }: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
