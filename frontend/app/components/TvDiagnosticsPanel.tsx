import React, { useState } from "react";
import { CheckCircleIcon, ExclamationTriangleIcon, XCircleIcon } from "@heroicons/react/24/solid";
import { Button } from "./ui/button";
import { tvDiagnostics, TV_ART_ERROR_HELP, type TVDiagnostics } from "../utils/tvApi";

type Verdict = "ok" | "warn" | "fail";

function Row({ verdict, label, children }: { verdict: Verdict; label: string; children: React.ReactNode }) {
  const Icon = verdict === "ok" ? CheckCircleIcon : verdict === "warn" ? ExclamationTriangleIcon : XCircleIcon;
  const color =
    verdict === "ok" ? "text-emerald-500" : verdict === "warn" ? "text-amber-500" : "text-red-500";
  return (
    <li className="flex items-start gap-2">
      <Icon className={`h-4 w-4 mt-0.5 flex-shrink-0 ${color}`} aria-hidden />
      <div className="min-w-0">
        <span className="font-medium text-foreground">{label}</span>
        <span className="text-muted-foreground"> — {children}</span>
      </div>
    </li>
  );
}

/**
 * "Test connection" for one TV: the network answer, then one art session that reads the
 * API version, Art Mode and artwork count. It reads only, and changes nothing on the TV.
 */
export default function TvDiagnosticsPanel({ ip }: { ip: string }) {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<TVDiagnostics | null>(null);
  const [failure, setFailure] = useState("");

  const run = async () => {
    setRunning(true);
    setFailure("");
    try {
      setResult(await tvDiagnostics(ip));
    } catch (e: any) {
      setResult(null);
      setFailure(e.message || "Failed to test the connection");
    } finally {
      setRunning(false);
    }
  };

  const probe = result?.probe;
  const art = result?.art;
  // Some firmware reports "standby" while the TV is showing art. The app reads Art Mode
  // from the art channel instead, so the mismatch is worth explaining, not alarming.
  const standbyQuirk = !!art?.art_mode && probe?.reported_power_state === "standby";

  return (
    <div className="mb-4">
      <Button onClick={run} disabled={running} className="w-full text-sm">
        {running ? "Testing…" : "Test connection"}
      </Button>

      {failure && <p className="mt-2 text-xs text-red-600 dark:text-red-400">{failure}</p>}

      {result && probe && (
        <ul className="mt-3 space-y-2 rounded-lg border border-border bg-muted/30 p-3 text-xs" aria-live="polite">
          <Row verdict={probe.reachable ? "ok" : "fail"} label="Network">
            {probe.reachable ? `answers in ${probe.latency_ms} ms` : "no answer from this address"}
          </Row>

          {probe.reachable && (
            <Row verdict={probe.frame_tv_support ? "ok" : "warn"} label="Model">
              {probe.model || "unknown"}
              {probe.frame_tv_support ? "" : " (does not report Frame TV support)"}
            </Row>
          )}

          {result.art_error ? (
            <Row verdict="fail" label="Art channel">
              {TV_ART_ERROR_HELP[result.art_error]}
            </Row>
          ) : art ? (
            <>
              <Row verdict="ok" label="Art channel">
                API {art.api_version || "unknown"}, Art Mode {art.art_mode ? "on" : "off"}
                {art.artwork_count !== null ? `, ${art.artwork_count} artworks` : ""}
              </Row>
              {standbyQuirk && (
                <Row verdict="warn" label="Reported state">
                  the TV says "standby" while showing art. This is a known firmware quirk and does not affect the app.
                </Row>
              )}
            </>
          ) : null}

          <Row verdict={result.has_mac ? "ok" : "warn"} label="Wake-on-LAN">
            {result.has_mac
              ? "MAC address saved"
              : "no MAC address saved, so the app cannot wake this TV when it is off"}
          </Row>
        </ul>
      )}
    </div>
  );
}
