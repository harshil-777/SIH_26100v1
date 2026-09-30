import { Bookmark, FileStack, LayoutDashboard, Menu, ShieldCheck, X, type LucideIcon } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { GlobalSearch } from "@/components/layout/GlobalSearch";
import { api, MARKS_CHANGED } from "@/lib/api";
import { initials } from "@/lib/format";
import { readOfficer } from "@/lib/officer";
import { auditHref, markedHref, overviewHref, tendersHref, type Route } from "@/lib/router";
import { cn } from "@/lib/utils";

type Section = "overview" | "tenders" | "marked" | "audit";

const NAV: { section: Section; label: string; href: string; icon: LucideIcon }[] = [
  { section: "overview", label: "Overview", href: overviewHref, icon: LayoutDashboard },
  { section: "tenders", label: "Tenders", href: tendersHref, icon: FileStack },
  { section: "marked", label: "Marked bids", href: markedHref, icon: Bookmark },
  { section: "audit", label: "Audit trail", href: auditHref, icon: ShieldCheck },
];

const sectionOf = (route: Route): Section =>
  route.name === "tender" || route.name === "bid" ? "tenders" : route.name;

export function AppShell({ route, children }: { route: Route; children: ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => setDrawerOpen(false), [route]);

  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 lg:block">
        <Sidebar active={sectionOf(route)} />
      </aside>

      {drawerOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm animate-in fade-in-0" onClick={() => setDrawerOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 max-w-[85vw] animate-in slide-in-from-left duration-200">
            <Sidebar active={sectionOf(route)} onClose={() => setDrawerOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-h-screen flex-col lg:pl-64">
        <TopBar onMenu={() => setDrawerOpen(true)} />
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</main>
        <footer className="border-t border-slate-200/80 px-4 py-5 text-xs text-slate-500 sm:px-6 lg:px-8">
          <div className="mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-2">
            <span>Bid-Auth · Compliance verification for Government e-Marketplace procurement</span>
            <span>Rule engine is the decision of record · AI output is advisory only</span>
          </div>
        </footer>
      </div>
    </div>
  );
}

export function LogoMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 shadow-sm ring-1 ring-inset ring-white/15",
        className,
      )}
    >
      <ShieldCheck className="h-5 w-5 text-white" strokeWidth={2.25} aria-hidden />
    </span>
  );
}

function useMarkedCount(): number | null {
  const [count, setCount] = useState<number | null>(null);
  useEffect(() => {
    const refresh = () => api.listMarks().then((marks) => setCount(marks.length), () => {});
    refresh();
    window.addEventListener(MARKS_CHANGED, refresh);
    return () => window.removeEventListener(MARKS_CHANGED, refresh);
  }, []);
  return count;
}

function Sidebar({ active, onClose }: { active: Section; onClose?: () => void }) {
  const markedCount = useMarkedCount();
  return (
    <div className="flex h-full flex-col bg-brand-950 text-slate-300">
      <div className="flex h-16 shrink-0 items-center gap-3 border-b border-white/[0.06] px-5">
        <a href={overviewHref} className="flex items-center gap-3">
          <LogoMark />
          <span>
            <span className="block text-[15px] font-semibold leading-tight tracking-tight text-white">Bid-Auth</span>
            <span className="block text-[11px] leading-tight text-slate-400">GeM bid compliance</span>
          </span>
        </a>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="ml-auto rounded-md p-1.5 text-slate-400 hover:bg-white/10 hover:text-white"
            aria-label="Close navigation"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-5" aria-label="Main">
        <div className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Workspace</div>
        {NAV.map(({ section, label, href, icon: Icon }) => {
          const isActive = active === section;
          return (
            <a
              key={section}
              href={href}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive ? "bg-white/[0.08] text-white" : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-100",
              )}
            >
              {isActive && <span className="absolute inset-y-1.5 left-0 w-[3px] rounded-r-full bg-brand-400" aria-hidden />}
              <Icon className={cn("h-[18px] w-[18px]", isActive ? "text-brand-300" : "text-slate-500 group-hover:text-slate-300")} />
              {label}
              {section === "marked" && markedCount !== null && markedCount > 0 && (
                <span className="ml-auto rounded-md bg-brand-500/25 px-1.5 py-0.5 text-[11px] font-semibold tabular-nums text-brand-200">
                  {markedCount}
                </span>
              )}
            </a>
          );
        })}
      </nav>

      <SystemStatus />
    </div>
  );
}

function SystemStatus() {
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    const check = () =>
      api.health().then(
        () => !cancelled && setOnline(true),
        () => !cancelled && setOnline(false),
      );
    check();
    const timer = window.setInterval(check, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <div className="m-3 rounded-xl border border-white/[0.06] bg-white/[0.03] p-3.5 text-xs">
      <div className="flex items-center gap-2 font-medium text-slate-200">
        <span className="relative flex h-2 w-2">
          {online && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />}
          <span
            className={cn(
              "relative inline-flex h-2 w-2 rounded-full",
              online === null ? "bg-slate-500" : online ? "bg-emerald-400" : "bg-red-500",
            )}
          />
        </span>
        {online === null ? "Connecting…" : online ? "Verification service online" : "Service unreachable"}
      </div>
      <dl className="mt-2.5 space-y-1.5 text-slate-400">
        <div className="flex justify-between gap-2">
          <dt>Rule engine</dt>
          <dd className="text-slate-300">Decision of record</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>AI models</dt>
          <dd className="text-slate-300">Advisory</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Audit log</dt>
          <dd className="text-slate-300">SHA-256 chained</dd>
        </div>
      </dl>
    </div>
  );
}

function TopBar({ onMenu }: { onMenu: () => void }) {
  const officer = readOfficer();
  return (
    <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[1400px] items-center gap-3 px-4 sm:px-6 lg:px-8">
        <button
          type="button"
          onClick={onMenu}
          className="-ml-1.5 rounded-md p-1.5 text-slate-600 hover:bg-slate-100 lg:hidden"
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </button>
        <a href={overviewHref} className="flex items-center gap-2 lg:hidden">
          <LogoMark className="h-8 w-8" />
          <span className="hidden text-[15px] font-semibold tracking-tight sm:inline">Bid-Auth</span>
        </a>

        <div className="min-w-0 flex-1 sm:max-w-md lg:max-w-lg">
          <GlobalSearch />
        </div>

        <div className="ml-auto hidden items-center gap-2.5 sm:flex">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-800">
            {officer ? initials(officer) || "PO" : "PO"}
          </span>
          <span className="hidden text-left leading-tight md:block">
            <span className="block max-w-[12rem] truncate text-sm font-medium text-slate-900">{officer || "Procurement officer"}</span>
            <span className="block text-xs text-slate-500">Evaluation committee</span>
          </span>
        </div>
      </div>
    </header>
  );
}

