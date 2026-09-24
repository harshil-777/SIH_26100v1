import { useEffect, useState } from "react";

// Two views don't justify a router dependency: "#/" is the bid list, "#/bids/<id>" a bid.
export type Route = { name: "list" } | { name: "bid"; bidId: string };

function parse(hash: string): Route {
  const match = hash.match(/^#\/bids\/(.+)$/);
  return match ? { name: "bid", bidId: decodeURIComponent(match[1]) } : { name: "list" };
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
