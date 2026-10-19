import React, { useEffect, useState } from "react";
import { useLocation } from "react-router";
import { getTvs, tvReachability, type TVInfo } from "../utils/tvApi";

// The check reads the TV's plain HTTP endpoint only, so it never takes the single art
// channel away from an upload. Even so, a slow poll is plenty for a status light.
const POLL_MS = 30_000;

type Light = "checking" | "online" | "offline";

const COLORS: Record<Light, string> = {
  checking: "bg-gray-400 animate-pulse",
  online: "bg-emerald-500",
  offline: "bg-red-500",
};

const LABELS: Record<Light, string> = {
  checking: "checking…",
  online: "reachable",
  offline: "not answering",
};

/**
 * One light per TV in the header: green when the TV answers on the network, red when it
 * does not. A red light before an upload explains a failure before it happens.
 */
export default function TvStatusIndicator() {
  const [tvs, setTvs] = useState<TVInfo[]>([]);
  const [lights, setLights] = useState<Record<string, Light>>({});

  // The header outlives page changes, so the list is read again on each one: a TV added
  // or removed in Settings shows up without reloading the page.
  const { pathname } = useLocation();

  useEffect(() => {
    let cancelled = false;
    getTvs()
      .then((list: TVInfo[]) => !cancelled && setTvs(list || []))
      .catch(() => !cancelled && setTvs([]));
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  useEffect(() => {
    if (tvs.length === 0) return;
    let cancelled = false;

    const check = async () => {
      // A hidden tab has nobody to tell, and the TV does not need the traffic.
      if (document.visibilityState === "hidden") return;
      const results = await Promise.all(
        tvs.map(async (tv): Promise<[string, Light]> => {
          try {
            return [tv.ip, (await tvReachability(tv.ip)).reachable ? "online" : "offline"];
          } catch {
            return [tv.ip, "offline"];
          }
        })
      );
      if (!cancelled) setLights(Object.fromEntries(results));
    };

    check();
    const timer = window.setInterval(check, POLL_MS);
    document.addEventListener("visibilitychange", check);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", check);
    };
  }, [tvs]);

  if (tvs.length === 0) return null;

  return (
    <div className="flex items-center gap-2" aria-label="TV connection status">
      {tvs.map((tv) => {
        const light = lights[tv.ip] ?? "checking";
        const name = tv.name || tv.ip;
        return (
          <span
            key={tv.ip}
            className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-300"
            title={`${name}: ${LABELS[light]}`}
          >
            <span className={`inline-block h-2.5 w-2.5 rounded-full ${COLORS[light]}`} />
            {/* The name only shows when there is room, and the light alone carries the state. */}
            <span className="hidden sm:inline max-w-24 truncate">{name}</span>
            <span className="sr-only">{LABELS[light]}</span>
          </span>
        );
      })}
    </div>
  );
}
