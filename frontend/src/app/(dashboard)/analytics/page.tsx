"use client";

import { AlertTriangle, BarChart3, CheckCheck, Clock, MessageSquare, Send } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { AiImpactCard } from "@/components/analytics-ai-impact";
import { AiInsightsCard } from "@/components/analytics-ai-insights";
import { AiPerformanceCard } from "@/components/analytics-ai-performance";
import { ExecutiveSummary } from "@/components/analytics-executive-summary";
import { HealthScore } from "@/components/analytics-health-score";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { ActivityDot } from "@/components/ui/activity-dot";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DonutChart } from "@/components/ui/donut-chart";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendChart } from "@/components/ui/trend-chart";
import { useAnalyticsDashboard } from "@/hooks/use-analytics";
import { periodTrendPct } from "@/lib/analytics-insights";
import { APPOINTMENT_STATUS, APPOINTMENT_STATUS_BADGE } from "@/lib/appointments";
import { CONVERSATION_STATUS_BADGE } from "@/lib/conversations";
import { STAGE_LABEL } from "@/lib/leads";
import { VARIANT_TO_STATE } from "@/lib/status";
import type {
  AnalyticsDashboard,
  AnalyticsRange,
  AnalyticsTrendPoint,
  Appointment,
  Conversation,
  LeadStage,
} from "@/lib/types";

const RANGE_OPTIONS: { label: string; value: AnalyticsRange }[] = [
  { label: "7d", value: "7d" },
  { label: "30d", value: "30d" },
  { label: "90d", value: "90d" },
];

const RANGE_PERIOD_LABEL: Record<AnalyticsRange, string> = {
  "7d": "Last 7 Days",
  "30d": "Last 30 Days",
  "90d": "Last 90 Days",
};

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  return `${Math.round(minutes / 60)}h`;
}

// Sprint 85 stagger — each top-level section fades/slides in with a small
// per-index delay via the existing animate-fade-in-up utility. Fill-mode
// "backwards" is set inline (not in the shared utility) so this section
// stays hidden through its own delay window instead of flashing visible
// then re-animating; globals.css's reduced-motion guard forces both
// animation-duration and animation-delay to ~0, so this collapses to an
// instant, undelayed reveal for anyone who's asked for reduced motion.
function reveal(index: number): React.CSSProperties {
  return { animationDelay: `${index * 60}ms`, animationFillMode: "backwards" };
}

export default function AnalyticsPage() {
  const [range, setRange] = useState<AnalyticsRange>("30d");
  const { data, isPending, isError, refetch, isFetching } = useAnalyticsDashboard(range);

  return (
    <>
      <PageHeader
        title="Analytics"
        description="How your AI employee is performing."
        action={
          <div className="flex gap-1">
            {RANGE_OPTIONS.map((opt) => (
              <Button
                key={opt.value}
                size="sm"
                variant={range === opt.value ? "secondary" : "ghost"}
                onClick={() => setRange(opt.value)}
              >
                {opt.label}
              </Button>
            ))}
          </div>
        }
      />

      {isPending && (
        <div className="space-y-4">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-8 w-2/3" />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-28 w-full" />
            ))}
          </div>
          <Skeleton className="h-72 w-full" />
        </div>
      )}

      {isError && (
        <EmptyState
          icon={AlertTriangle}
          title="Couldn't load analytics"
          description="Something went wrong — please try again."
          action={
            <Button size="sm" onClick={() => refetch()} disabled={isFetching}>
              {isFetching ? "Retrying…" : "Retry"}
            </Button>
          }
        />
      )}

      {!isPending && !isError && data && data.overview.total_conversations === 0 && (
        <EmptyState
          icon={BarChart3}
          title="Analytics unlock as conversations come in"
          description="No fake tiles. Every section here appears the moment there's real data behind it."
        />
      )}

      {!isPending && !isError && data && data.overview.total_conversations > 0 && (
        <AnalyticsContent data={data} range={range} />
      )}
    </>
  );
}

function AnalyticsContent({ data, range }: { data: AnalyticsDashboard; range: AnalyticsRange }) {
  const leadsTotal = Object.values(data.business_health.leads_by_stage).reduce((a, b) => a + b, 0);
  const appointmentsTotal = Object.values(data.business_health.appointments_by_status).reduce((a, b) => a + b, 0);
  const convDelta = periodTrendPct(data.trends.conversations);
  const responseSlow =
    data.overview.avg_response_time_seconds !== null && data.overview.avg_response_time_seconds > 600;

  return (
    <div className="space-y-6">
      <div className="animate-fade-in-up" style={reveal(0)}>
        <ExecutiveSummary data={data} />
      </div>

      <div className="animate-fade-in-up" style={reveal(1)}>
        <HealthScore data={data} />
      </div>

      {/* KPI strip — Total conversations leads at a larger size; the other
          four are today-only snapshots, so they get an honest "Today"
          period instead of a fabricated delta. */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6 animate-fade-in-up" style={reveal(2)}>
        <div className="lg:col-span-2">
          <StatCard
            label="Total conversations"
            countTo={data.overview.total_conversations}
            icon={MessageSquare}
            period={RANGE_PERIOD_LABEL[range]}
            delta={convDelta !== null ? { pct: Math.abs(convDelta), direction: convDelta >= 0 ? "up" : "down" } : null}
            sparkline={data.trends.conversations}
            value={data.overview.total_conversations}
          />
        </div>
        <StatCard
          label="Messages today"
          countTo={data.overview.messages_today}
          icon={Send}
          period="Today"
          sparkline={data.trends.messages}
          value={data.overview.messages_today}
        />
        <StatCard
          label="AI responses today"
          countTo={data.overview.ai_responses_today}
          icon={CheckCheck}
          period="Today"
          value={data.overview.ai_responses_today}
        />
        <StatCard
          label="Failed responses today"
          countTo={data.overview.failed_responses_today}
          icon={AlertTriangle}
          period="Today"
          tone="warning"
          value={data.overview.failed_responses_today}
        />
        <StatCard
          label="Avg response time"
          icon={Clock}
          period="Today"
          value={formatDuration(data.overview.avg_response_time_seconds)}
        />
      </div>

      {/* Hero — Conversation Trend, the page's visual centerpiece. */}
      <Card interactive className="shadow-e3 animate-fade-in-up" style={reveal(3)}>
        <CardHeader className="flex-row items-baseline justify-between space-y-0">
          <CardTitle className="text-base">Conversation trend</CardTitle>
          <span className="text-xs text-muted-foreground">{RANGE_PERIOD_LABEL[range]}</span>
        </CardHeader>
        <CardContent>
          <TrendChart title="Conversations over time" data={data.trends.conversations} variant="hero" />
        </CardContent>
      </Card>

      {/* Coverage + Response Health */}
      <div className="grid gap-4 lg:grid-cols-2 animate-fade-in-up" style={reveal(4)}>
        <Card interactive>
          <CardHeader>
            <CardTitle className="text-base">AI coverage</CardTitle>
          </CardHeader>
          <CardContent>
            <DonutChart
              title="AI coverage"
              segments={[
                { key: "handled", label: "Handled by AI", value: data.ai_impact.conversations_handled, state: "success" },
                { key: "escalated", label: "Escalated to human", value: data.ai_impact.human_escalations, state: "waiting" },
              ]}
            />
          </CardContent>
        </Card>

        <Card interactive>
          <CardHeader>
            <CardTitle className="text-base">Response health</CardTitle>
          </CardHeader>
          {/* Qualitative status, not a second copy of the KPI strip's raw
              numbers — those already show "Failed responses today" and
              "Avg response time" as bare figures above; repeating them here
              verbatim would be redundant on the page and ambiguous to a
              screen reader. This card answers "is it healthy", not "what's
              the number". */}
          <CardContent className="space-y-3">
            <div className="flex items-center gap-2.5 text-sm">
              <ActivityDot state={data.overview.failed_responses_today > 0 ? "error" : "success"} />
              {data.overview.failed_responses_today > 0
                ? `${data.overview.failed_responses_today} response${data.overview.failed_responses_today === 1 ? "" : "s"} failed today`
                : "No failed responses today"}
            </div>
            <div className="flex items-center gap-2.5 text-sm">
              <ActivityDot state={responseSlow ? "waiting" : "success"} />
              {responseSlow
                ? `Slower than usual — ${formatDuration(data.overview.avg_response_time_seconds)} avg`
                : `Responding in ${formatDuration(data.overview.avg_response_time_seconds)} on average`}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="animate-fade-in-up" style={reveal(5)}>
        <AiImpactCard impact={data.ai_impact} range={range} />
      </div>

      <div className="animate-fade-in-up" style={reveal(6)}>
        <AiInsightsCard data={data} />
      </div>

      <div className="animate-fade-in-up" style={reveal(7)}>
        <h2 className="mb-3 text-sm font-medium text-muted-foreground">Trends</h2>
        <div className="grid gap-4 lg:grid-cols-3">
          <Card interactive>
            <TrendCardHeader title="Messages over time" data={data.trends.messages} />
            <CardContent>
              <TrendChart title="Messages over time" data={data.trends.messages} />
            </CardContent>
          </Card>
          <Card interactive>
            <TrendCardHeader title="Leads over time" data={data.trends.leads} />
            <CardContent>
              <TrendChart title="Leads over time" data={data.trends.leads} />
            </CardContent>
          </Card>
          <Card interactive>
            <TrendCardHeader title="Appointments over time" data={data.trends.appointments} />
            <CardContent>
              <TrendChart title="Appointments over time" data={data.trends.appointments} />
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="animate-fade-in-up" style={reveal(8)}>
        <h2 className="mb-3 text-sm font-medium text-muted-foreground">Business breakdowns</h2>
        <div className="grid gap-4 lg:grid-cols-3">
          <Card interactive>
            <CardHeader className="flex-row items-baseline justify-between space-y-0">
              <CardTitle className="text-base">Conversations by status</CardTitle>
              <span className="text-xs text-muted-foreground">this period</span>
            </CardHeader>
            <CardContent>
              <DonutChart
                title="Conversations by status"
                segments={Object.entries(data.business_health.conversations_by_status).map(
                  ([key, value]) => {
                    const badge = CONVERSATION_STATUS_BADGE[key as Conversation["status"]];
                    return {
                      key,
                      label: badge?.label ?? key,
                      value,
                      state: VARIANT_TO_STATE[badge?.variant ?? "secondary"],
                    };
                  },
                )}
              />
            </CardContent>
          </Card>

          <Card interactive>
            <CardHeader className="flex-row items-baseline justify-between space-y-0">
              <CardTitle className="text-base">Leads by stage</CardTitle>
              <span className="text-xs text-muted-foreground">full pipeline</span>
            </CardHeader>
            <CardContent className="space-y-4">
              {leadsTotal === 0 ? (
                <EmptyState
                  icon={BarChart3}
                  title="No leads yet"
                  description="HIRA creates a lead automatically when a conversation shows buying intent."
                  className="py-8"
                  action={
                    <Button asChild size="sm" variant="outline">
                      <Link href="/leads">View Leads</Link>
                    </Button>
                  }
                />
              ) : (
                <>
                  <p className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-[11px] text-muted-foreground">
                    Ordered pipeline — kept as a bar; 7 sequential stages read better as a funnel than a
                    donut
                  </p>
                  <BreakdownList
                    entries={Object.entries(data.business_health.leads_by_stage)}
                    labelFor={(key) => STAGE_LABEL[key as LeadStage] ?? key}
                  />
                  {Object.keys(data.business_health.leads_by_source).length > 0 && (
                    <>
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        By source
                      </p>
                      <BreakdownList entries={Object.entries(data.business_health.leads_by_source)} />
                    </>
                  )}
                </>
              )}
            </CardContent>
          </Card>

          <Card interactive>
            <CardHeader className="flex-row items-baseline justify-between space-y-0">
              <CardTitle className="text-base">Appointments by status</CardTitle>
              <span className="text-xs text-muted-foreground">this period</span>
            </CardHeader>
            <CardContent>
              {appointmentsTotal === 0 ? (
                <EmptyState
                  icon={BarChart3}
                  title="No appointments booked"
                  description="These appear once HIRA books one from a conversation, or you connect Google Calendar."
                  className="py-8"
                  action={
                    <Button asChild size="sm" variant="outline">
                      <Link href="/calendar">Go to Calendar</Link>
                    </Button>
                  }
                />
              ) : (
                <DonutChart
                  title="Appointments by status"
                  segments={Object.entries(data.business_health.appointments_by_status).map(
                    ([key, value]) => ({
                      key,
                      label: APPOINTMENT_STATUS_BADGE[key as Appointment["status"]]?.label ?? key,
                      value,
                      state: APPOINTMENT_STATUS[key as Appointment["status"]] ?? "idle",
                    }),
                  )}
                />
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <div id="ai-performance" className="animate-fade-in-up" style={reveal(9)}>
        <AiPerformanceCard data={data.ai_performance} />
      </div>
    </div>
  );
}

// Headline total + within-period delta above each trend chart — the same
// "state the value directly, don't make hover mandatory" principle as
// TrendChart's own endpoint badge, one level up. The delta compares the
// back half of the fetched range to the front half (the only comparison
// the API's single-range payload actually supports — see
// lib/analytics-insights.ts), never a fabricated "vs last period" claim.
function TrendCardHeader({ title, data }: { title: string; data: AnalyticsTrendPoint[] }) {
  const total = data.reduce((sum, p) => sum + p.count, 0);
  const delta = periodTrendPct(data);
  return (
    <CardHeader className="flex-row items-baseline justify-between space-y-0">
      <CardTitle className="text-base">{title}</CardTitle>
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-lg font-semibold tabular-nums">{total}</span>
        {delta !== null && (
          <span className={`type-caption font-semibold ${delta >= 0 ? "text-success" : "text-muted-foreground"}`}>
            {delta >= 0 ? "↑" : "↓"} {Math.abs(delta)}%
          </span>
        )}
      </div>
    </CardHeader>
  );
}

function BreakdownList({
  entries,
  labelFor,
}: {
  entries: [string, number][];
  labelFor?: (key: string) => string;
}) {
  if (entries.length === 0) {
    return <p className="text-sm text-muted-foreground">No data yet.</p>;
  }
  const max = Math.max(...entries.map(([, count]) => count));
  return (
    <ul className="space-y-2.5">
      {entries.map(([key, count]) => (
        <li key={key} className="space-y-1">
          <div className="flex items-center justify-between text-sm">
            <span className="capitalize">{labelFor ? labelFor(key) : key}</span>
            <span className="tabular-nums text-muted-foreground">{count}</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-foreground/75 transition-[width] duration-700 ease-out"
              style={{ width: `${max > 0 ? (count / max) * 100 : 0}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
