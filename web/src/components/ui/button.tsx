import { cva, type VariantProps } from "class-variance-authority";
import type { AnchorHTMLAttributes, ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-brand-600 text-white shadow-sm hover:bg-brand-700 active:bg-brand-800",
        outline: "border border-slate-300 bg-white text-slate-800 shadow-sm hover:border-slate-400 hover:bg-slate-50",
        ghost: "text-slate-700 hover:bg-slate-100",
        success: "bg-emerald-600 text-white shadow-sm hover:bg-emerald-700",
        danger: "bg-red-600 text-white shadow-sm hover:bg-red-700",
        warning: "bg-amber-500 text-white shadow-sm hover:bg-amber-600",
        inverse: "bg-white text-brand-950 shadow-sm hover:bg-brand-50",
        "inverse-outline": "border border-white/25 text-white hover:bg-white/10",
      },
      size: {
        sm: "h-8 px-3 text-[13px]",
        md: "h-9 px-4",
        lg: "h-11 px-5 text-[15px]",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

type Variants = VariantProps<typeof buttonVariants>;

export function Button({ className, variant, size, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & Variants) {
  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}

export function LinkButton({ className, variant, size, ...props }: AnchorHTMLAttributes<HTMLAnchorElement> & Variants) {
  return <a className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}
