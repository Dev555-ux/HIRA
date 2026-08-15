import { CheckCircle2, MessageSquare, ShieldAlert, Sparkles } from "lucide-react";
import Link from "next/link";
import { aiSurfaceClassName } from "@/components/ui/ai-surface";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { ALERT_HREF, ALERT_LABEL } from "@/lib/alerts";
import { aiCoveragePct, periodTrendPct } from "@/lib/analytics-insights";
import { cn } from "@/lib/utils";
import type { AnalyticsDashboard } from "@/lib/types";

// The 3-second read at the top of Analytics: what happened, what deserves
// attention, what did it save. Three columns, three real answers — no new
// endpoint, no LLM call, just arithmetic over the same AnalyticsDashboard
// the page already fetched. Sprint 84.3.
export function ExecutiveSummary({ data }: { data: AnalyticsDashboard }) {
  const { overview, ai_impact, business_health, trends } = data;
  const aiHandledPct = aiCoveragePct(overview, ai_impact);
  const trendPct = periodTrendPct(trends.conversations);

  return (
    <Card className={cn(aiSurfaceClassName, "shadow-e3")}>
      <CardHeader>
        <CardTitle className="text-base">This period, at a glance</CardTitle>
      </CardHeader>
      <div className="grid gap-8 p-6 pt-0 sm:grid-cols-3">
        <div>
          <div className="flex items-center gap-2 type-caption font-semibold uppercase tracking-wide text-muted-foreground">
            <MessageSquare className="size-3.5 text-brand" aria-hidden="true" />
            What happened
          </div>
          <p className="mt-2.5 text-4xl font-bold tracking-tight tabular-nums">
            {overview.total_conversations}
            {trendPct !== null && (
              <span className={cn("ml-2 text-lg font-semibold", trendPct >= 0 ? "text-success" : "text-muted-foreground")}>
                {trendPct >= 0 ? "↑" : "↓"} {Math.abs(trendPct)}%
              </span>
            )}
          </p>
          <p className="mt-1.5 text-sm text-muted-foreground">
            conversation{overview.total_conversations === 1 ? "" : "s"} ·{" "}
            {aiHandledPct === null
              ? "no conversations yet this period."
              : `AI handled ${aiHandledPct}% without a human.`}
            {trendPct !== null && (trendPct >= 0 ? " Picking up across this period." : " Slowing across this period.")}
          </p>
        </div>

        <div>
          <div className="flex items-center gap-2 type-caption font-semibold uppercase tracking-wide text-muted-foreground">
            <ShieldAlert className="size-3.5 text-brand" aria-hidden="true" />
            Deserves attention
          </div>
          {business_health.alerts.length === 0 ? (
            <div className="mt-2.5 flex items-center gap-2 text-2xl font-bold tracking-tight text-success">
              <CheckCircle2 className="size-6 shrink-0" aria-hidden="true" />
              All clear
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
          <p className="mt-1.5 text-sm text-muted-foreground">
            {business_health.alerts.length === 0
              ? "Nothing needs attention right now."
              : `${business_health.alerts.length} thing${business_health.alerts.length === 1 ? "" : "s"} to look at.`}
          </p>
        </div>

        <div>
          <div className="flex items-center gap-2 type-caption font-semibold uppercase tracking-wide text-muted-foreground">
            <Sparkles className="size-3.5 text-brand" aria-hidden="true" />
            Work saved
          </div>
          <p className="mt-2.5 text-4xl font-bold tracking-tight tabular-nums">≈{ai_impact.estimated_hours_saved}h</p>
          <p className="mt-1.5 text-sm text-muted-foreground">Estimated from AI-handled volume — not a measured benchmark.</p>
        </div>
      </div>
    </Card>
  );
}
