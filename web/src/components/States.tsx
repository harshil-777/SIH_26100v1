import { AlertTriangle, Inbox, RefreshCw, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export function ErrorState({ title = "Something went wrong", message, onRetry }: { title?: string; message: string; onRetry?: () => void }) {
  return (
    <Card className="flex flex-col items-center px-6 py-12 text-center">
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-red-50 text-red-600 ring-1 ring-inset ring-red-100">
        <AlertTriangle className="h-5 w-5" aria-hidden />
      </span>
      <h2 className="mt-4 text-base font-semibold text-slate-900">{title}</h2>
      <p className="mt-1 max-w-md text-sm text-slate-500">{message}</p>
      {onRetry && (
        <Button variant="outline" className="mt-5" onClick={onRetry}>
          <RefreshCw className="h-4 w-4" aria-hidden /> Try again
        </Button>
      )}
    </Card>
  );
}

export function EmptyState({ icon: Icon = Inbox, title, children }: { icon?: LucideIcon; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        <Icon className="h-5 w-5" aria-hidden />
      </span>
      <p className="mt-3 text-sm font-medium text-slate-900">{title}</p>
      {children && <div className="mt-1 max-w-sm text-sm text-slate-500">{children}</div>}
    </div>
  );
}
