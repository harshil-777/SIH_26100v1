import { AppShell } from "@/components/layout/AppShell";
import AuditPage from "@/pages/AuditPage";
import BidDetail from "@/pages/BidDetail";
import BidList from "@/pages/BidList";
import Overview from "@/pages/Overview";
import TenderDetail from "@/pages/TenderDetail";
import TenderList from "@/pages/TenderList";
import { useRoute } from "@/lib/router";

export default function App() {
  const route = useRoute();

  return (
    <AppShell route={route}>
      {route.name === "bid" ? (
        <BidDetail key={route.bidId} bidId={route.bidId} />
      ) : route.name === "tender" ? (
        <TenderDetail key={route.tenderId} tenderId={route.tenderId} />
      ) : route.name === "tenders" ? (
        <TenderList />
      ) : route.name === "bids" ? (
        // Keyed on the full hash so moving between #/bids and #/bids?status=awaiting re-applies the filter.
        <BidList key={window.location.hash} />
      ) : route.name === "audit" ? (
        <AuditPage />
      ) : (
        <Overview />
      )}
    </AppShell>
  );
}
