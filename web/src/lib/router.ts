import { useEffect, useState } from "react";

export type Route =
  | { name: "overview" }
  | { name: "tenders" }
  | { name: "tender"; tenderId: string }
  | { name: "bid"; bidId: string }
  | { name: "audit" };

function parse(hash: string): Route {
  const path = hash.replace(/^#/, "").split("?")[0].replace(/\/+$/, "");
  const bid = path.match(/^\/bids\/(.+)$/);
  if (bid) return { name: "bid", bidId: decodeURIComponent(bid[1]) };
  const tender = path.match(/^\/tenders\/(.+)$/);
  if (tender) return { name: "tender", tenderId: decodeURIComponent(tender[1]) };
  if (path === "/tenders") return { name: "tenders" };
  if (path === "/audit") return { name: "audit" };
  return { name: "overview" };
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parse(window.location.hash));
  useEffect(() => {
    const onChange = () => {
      setRoute(parse(window.location.hash));
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

export const navigate = (href: string) => {
  window.location.hash = href.replace(/^#/, "");
};

export const overviewHref = "#/";
export const tendersHref = "#/tenders";
export const auditHref = "#/audit";
export const tenderAuditHref = (tenderId: string) => `#/audit?tender=${encodeURIComponent(tenderId)}`;
export const hashParam = (key: string) => new URLSearchParams(window.location.hash.split("?")[1] ?? "").get(key);
export const bidHref = (bidId: string) => `#/bids/${encodeURIComponent(bidId)}`;
export const tenderHref = (tenderId: string) => `#/tenders/${encodeURIComponent(tenderId)}`;
