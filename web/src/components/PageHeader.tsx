import { ChevronRight } from "lucide-react";
import { Fragment, type ReactNode } from "react";

export type Crumb = { label: string; href?: string };

export function PageHeader({
  title,
  description,
  crumbs,
  actions,
  meta,
}: {
  title: ReactNode;
  description?: ReactNode;
  crumbs?: Crumb[];
  actions?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <div className="mb-6 space-y-3">
      {crumbs && crumbs.length > 0 && <Breadcrumbs crumbs={crumbs} />}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900 sm:text-[28px] sm:leading-9">{title}</h1>
          {description && <p className="mt-1.5 max-w-3xl text-[15px] text-slate-500">{description}</p>}
          {meta && <div className="mt-3">{meta}</div>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}

export function Breadcrumbs({ crumbs }: { crumbs: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-1 text-[13px] text-slate-500">
      {crumbs.map((crumb, i) => (
        <Fragment key={`${crumb.label}-${i}`}>
          {i > 0 && <ChevronRight className="h-3.5 w-3.5 text-slate-400" aria-hidden />}
          {crumb.href ? (
            <a href={crumb.href} className="rounded px-0.5 hover:text-brand-700 hover:underline">
              {crumb.label}
            </a>
          ) : (
            <span className="px-0.5 font-medium text-slate-700" aria-current="page">
              {crumb.label}
            </span>
          )}
        </Fragment>
      ))}
    </nav>
  );
}
