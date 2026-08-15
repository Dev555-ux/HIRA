import { StatusPill } from "@/components/ui/status-pill";
import { healthSignals } from "@/lib/analytics-insights";
import type { AnalyticsDashboard } from "@/lib/types";

// The Executive Health Score (Sprint 85, Analytics) — "is my business
// healthy?" in under five seconds. Deliberately not a Card: a system-status
// strip, not another block competing for attention. Every signal comes from
// healthSignals() in lib/analytics-insights.ts, which reads only fields
// AnalyticsDashboard already has — no new data, no new endpoint.
//
// Sprint 86: reused as-is on the Dashboard hero area too (originally named
// analytics-health-score.tsx; renamed here now that it's shared by two
// pages) — Dashboard's old BusinessHealthCard covered the same real
// signals (onboarding/WhatsApp/KB/alerts) less compactly, and had no other
// remaining caller once this replaced it, so it was deleted rather than
// kept as a second, divergent way to show the same thing.
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
