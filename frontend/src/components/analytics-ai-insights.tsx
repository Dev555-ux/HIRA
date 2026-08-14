import { AlertTriangle, CalendarDays, CheckCheck, TrendingUp } from "lucide-react";
import Link from "next/link";
import { aiSurfaceClassName } from "@/components/ui/ai-surface";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { dayOfWeekPeak } from "@/lib/analytics-insights";
import type { AnalyticsDashboard } from "@/lib/types";

interface Insight {
  kicker: "What happened" | "Why" | "What to do next";
  icon: typeof TrendingUp;
  body: React.ReactNode;
  action?: { label: string; href: string };
}

// What/Why/Next, each one traceable to a real field on AnalyticsDashboard.
// No LLM call — every sentence here is arithmetic over data the page
// already fetched. Sprint 84.3.
//
// Deliberately doesn't claim any period-over-period delta for escalations,
// KB coverage, or response time — the API has no prior-period baseline for
// those (only the four daily trend series do). Claiming "-25% vs last
// week" here would mean inventing a comparison number that doesn't exist.
export function AiInsightsCard({ data }: { data: AnalyticsDashboard }) {
  const { overview, ai_impact, trends } = data;

  if (overview.total_conversations === 0) {
    return null; // nothing to say yet — the page's own top-level empty state already covers this
  }

  const insights: Insight[] = [];

  const aiHandledPct = Math.round((ai_impact.conversations_handled / overview.total_conversations) * 100);
  insights.push({
    kicker: "What happened",
    icon: CheckCheck,
    body: (
      <>
        AI handled <b className="font-semibold">{aiHandledPct}%</b> of conversations this period — only{" "}
        <b className="font-semibold">{ai_impact.human_escalations}</b> needed a human.
      </>
    ),
  });

  const peakLeadDay = dayOfWeekPeak(trends.leads);
  if (peakLeadDay) {
    insights.push({
      kicker: "What happened",
      icon: CalendarDays,
      body: (
        <>
          Leads peaked on <b className="font-semibold">{peakLeadDay}s</b> this period.
        </>
      ),
      action: { label: "Check staffing & speed in Leads", href: "/leads" },
    });
  }

  if (ai_impact.ai_responses > 0) {
    const kbPct = Math.round((ai_impact.kb_grounded_replies / ai_impact.ai_responses) * 100);
    insights.push({
      kicker: "Why",
      icon: TrendingUp,
      body: (
        <>
          <b className="font-semibold">{kbPct}%</b> of AI responses were grounded in your Knowledge Base, while{" "}
          <b className="font-semibold">{ai_impact.human_escalations}</b> conversation
          {ai_impact.human_escalations === 1 ? "" : "s"} needed a human — a well-covered Knowledge Base tends to
          mean fewer escalations.
        </>
      ),
      action: { label: "Keep publishing to the Knowledge Base", href: "/knowledge-base" },
    });
  }

  if (overview.failed_responses_today > 0) {
    insights.push({
      kicker: "What to do next",
      icon: AlertTriangle,
      body: (
        <>
          <b className="font-semibold">{overview.failed_responses_today}</b> AI response
          {overview.failed_responses_today === 1 ? "" : "s"} failed today.
        </>
      ),
      action: { label: "Review in AI Performance", href: "#ai-performance" },
    });
  }

  return (
    <Card className={aiSurfaceClassName}>
      <CardHeader>
        <CardTitle className="text-base">AI Insights</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="relative space-y-1 before:absolute before:bottom-4 before:left-[15px] before:top-4 before:w-px before:bg-gradient-to-b before:from-brand/35 before:to-transparent">
          {insights.map((insight, i) => (
            <li key={i} className="relative flex items-start gap-3.5 py-2.5">
              <span className="z-10 flex size-8 shrink-0 items-center justify-center rounded-full bg-brand/15 ring-1 ring-inset ring-brand/20">
                <insight.icon className="size-3.5 text-brand" />
              </span>
              <div className="min-w-0">
                <p className="type-caption font-semibold uppercase tracking-wide text-brand">{insight.kicker}</p>
                <p className="mt-0.5 text-sm leading-relaxed">{insight.body}</p>
                {insight.action && (
                  <Link
                    href={insight.action.href}
                    className="mt-1 inline-flex items-center gap-1 text-sm font-semibold text-brand hover:underline"
                  >
                    {insight.action.label} →
                  </Link>
                )}
              </div>
            </li>
          ))}
        </ul>
        <p className="mt-4 border-t pt-3.5 text-xs text-muted-foreground">
          Computed from this period&apos;s data — no LLM call, no new endpoint.
        </p>
      </CardContent>
    </Card>
  );
}
