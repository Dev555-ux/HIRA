import { CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { aiSurfaceClassName } from "@/components/ui/ai-surface";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { ALERT_LABEL } from "@/lib/alerts";
import { periodTrendPct } from "@/lib/analytics-insights";
import type { AnalyticsDashboard, FounderAlert } from "@/lib/types";

// Where each alert actually gets fixed — same alert set business_health
// already computes (business_alerts() in app/services/analytics.py, shared
// with Ops via lib/alerts.ts), just pointed at a real route each time
// instead of only being displayed as a badge.
const ALERT_HREF: Record<FounderAlert, string> = {
  whatsapp_disconnected: "/connect-whatsapp",
  missing_knowledge_base: "/knowledge-base",
  ai_failures: "#ai-performance",
  no_recent_activity: "/inbox",
};

// The 3-second read at the top of Analytics: what happened, what deserves
// attention, what did it save. Three columns, three real answers — no new
// endpoint, no LLM call, just arithmetic over the same AnalyticsDashboard
// the page already fetched. Sprint 84.3.
export function ExecutiveSummary({ data }: { data: AnalyticsDashboard }) {
  const { overview, ai_impact, business_health, trends } = data;
  const aiHandledPct =
    overview.total_conversations > 0
      ? Math.round((ai_impact.conversations_handled / overview.total_conversations) * 100)
      : null;
  const trendPct = periodTrendPct(trends.conversations);

  return (
    <Card className={aiSurfaceClassName}>
      <CardHeader>
        <CardTitle className="text-base">This period, at a glance</CardTitle>
      </CardHeader>
      <div className="grid divide-y sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        <div className="p-6 pt-0 sm:pt-6">
          <p className="type-caption font-semibold uppercase tracking-wide text-muted-foreground">
            What happened
          </p>
          <p className="mt-2 text-lg font-semibold tracking-tight tabular-nums">
            {overview.total_conversations} conversation{overview.total_conversations === 1 ? "" : "s"}
            {trendPct !== null && (
              <span className={trendPct >= 0 ? "text-success" : "text-muted-foreground"}>
                {" "}
                {trendPct >= 0 ? "↑" : "↓"} {Math.abs(trendPct)}%
              </span>
            )}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {aiHandledPct === null
              ? "No conversations yet this period."
              : `AI handled ${aiHandledPct}% of them without a human.`}
            {trendPct !== null && (trendPct >= 0 ? " Picking up across this period." : " Slowing across this period.")}
          </p>
        </div>

        <div className="p-6 pt-0 sm:pt-6">
          <p className="type-caption font-semibold uppercase tracking-wide text-muted-foreground">
            Deserves attention
          </p>
          {business_health.alerts.length === 0 ? (
            <div className="mt-2 flex items-center gap-2 text-sm font-medium text-success">
              <CheckCircle2 className="size-4 shrink-0" />
              All clear — nothing needs attention.
            </div>
          ) : (
            <ul className="mt-2 space-y-1">
              {business_health.alerts.map((alert) => (
                <li key={alert}>
                  <Link
                    href={ALERT_HREF[alert]}
                    className="flex items-center gap-2 rounded-md py-1 text-sm hover:text-brand"
                  >
                    <span className="size-1.5 shrink-0 rounded-full bg-warning" />
                    <span className="flex-1 font-medium">{ALERT_LABEL[alert]}</span>
                    <span className="text-xs font-semibold text-brand">Fix →</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="p-6 pt-0 sm:pt-6">
          <p className="type-caption font-semibold uppercase tracking-wide text-muted-foreground">
            Work saved
          </p>
          <p className="mt-2 text-lg font-semibold tracking-tight tabular-nums">
            ≈{ai_impact.estimated_hours_saved}h
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Estimated from AI-handled volume — not a measured benchmark.
          </p>
        </div>
      </div>
    </Card>
  );
}
