import { useEffect, useState } from "react";

export type Route =
  | { name: "tenders" }
  | { name: "tender"; tenderId: string }
  | { name: "bid"; bidId: string };

function parse(hash: string): Route {
  const bid = hash.match(/^#\/bids\/(.+)$/);
  if (bid) return { name: "bid", bidId: decodeURIComponent(bid[1]) };
  const tender = hash.match(/^#\/tenders\/(.+)$/);
  if (tender) return { name: "tender", tenderId: decodeURIComponent(tender[1]) };
  return { name: "tenders" };
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

export const bidHref = (bidId: string) => `#/bids/${encodeURIComponent(bidId)}`;
export const tenderHref = (tenderId: string) => `#/tenders/${encodeURIComponent(tenderId)}`;
