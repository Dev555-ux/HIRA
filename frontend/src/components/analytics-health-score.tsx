import { StatusPill } from "@/components/ui/status-pill";
import { healthSignals } from "@/lib/analytics-insights";
import type { AnalyticsDashboard } from "@/lib/types";

// The Executive Health Score (Sprint 85) — "is my business healthy?" in
// under five seconds, sitting right below Executive Summary. Deliberately
// not a Card: a system-status strip, not another block competing for
// attention. Every signal comes from healthSignals() in
// lib/analytics-insights.ts, which reads only fields AnalyticsDashboard
// already has — no new data, no new endpoint.
export function HealthScore({ data }: { data: AnalyticsDashboard }) {
  const signals = healthSignals(data);
  return (
    <div className="flex flex-wrap items-center gap-2" role="list" aria-label="Business health signals">
      {signals.map((signal) => (
        <div key={signal.key} role="listitem">
          <StatusPill state={signal.state}>{signal.label}</StatusPill>
        </div>
      ))}
    </div>
  );
}
