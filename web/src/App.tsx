import { ShieldCheck } from "lucide-react";
import BidDetail from "@/pages/BidDetail";
import BidList from "@/pages/BidList";
import { useRoute } from "@/lib/router";

export default function App() {
  const route = useRoute();

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-2 px-4 sm:px-6">
          <a href="#/" className="flex items-center gap-2 font-semibold text-slate-900">
            <ShieldCheck className="h-5 w-5 text-emerald-700" aria-hidden />
            GeM Bid Compliance
          </a>
          <span className="ml-2 hidden text-sm text-slate-500 sm:inline">Procurement officer dashboard</span>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        {route.name === "bid" ? <BidDetail key={route.bidId} bidId={route.bidId} /> : <BidList />}
      </main>
    </div>
  );
}
