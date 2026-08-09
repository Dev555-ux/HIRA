"use client";

import { AlertTriangle, BarChart3, CheckCheck, Clock, MessageSquare, Send } from "lucide-react";
import { useState } from "react";
import { AiMetricsSummary } from "@/components/ai-metrics-section";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { aiSurfaceClassName } from "@/components/ui/ai-surface";
import { BusinessHealthCard } from "@/components/ui/business-health-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendChart } from "@/components/ui/trend-chart";
import { useAnalyticsDashboard } from "@/hooks/use-analytics";
import { APPOINTMENT_STATUS_BADGE } from "@/lib/appointments";
import { CONVERSATION_STATUS_BADGE } from "@/lib/conversations";
import { STAGE_LABEL } from "@/lib/leads";
import type { AnalyticsRange, Appointment, Conversation, LeadStage } from "@/lib/types";

const RANGE_OPTIONS: { label: string; value: AnalyticsRange }[] = [
  { label: "7d", value: "7d" },
  { label: "30d", value: "30d" },
  { label: "90d", value: "90d" },
];

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  return `${Math.round(minutes / 60)}h`;
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
          <Skeleton className="h-24 w-full" />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-28 w-full" />
            ))}
          </div>
          <Skeleton className="h-40 w-full" />
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
        <div className="space-y-6">
          <BusinessHealthCard health={data.business_health} />

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <StatCard
              label="Total conversations"
              value={data.overview.total_conversations}
              icon={MessageSquare}
            />
            <StatCard label="Messages today" value={data.overview.messages_today} icon={Send} />
            <StatCard
              label="AI responses today"
              value={data.overview.ai_responses_today}
              icon={CheckCheck}
            />
            <StatCard
              label="Failed responses today"
              value={data.overview.failed_responses_today}
              icon={AlertTriangle}
            />
            <StatCard
              label="Avg response time"
              value={formatDuration(data.overview.avg_response_time_seconds)}
              icon={Clock}
            />
          </div>

          <Card className={aiSurfaceClassName}>
            <CardHeader>
              <CardTitle className="text-base">AI Impact · last {range}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <AiImpactStat label="Conversations handled" value={data.ai_impact.conversations_handled} />
                <AiImpactStat label="Escalated to a human" value={data.ai_impact.human_escalations} />
                <AiImpactStat label="Leads created" value={data.ai_impact.leads_created} />
                <AiImpactStat label="Appointments booked" value={data.ai_impact.appointments_booked} />
                <AiImpactStat label="KB-grounded replies" value={data.ai_impact.kb_grounded_replies} />
                <AiImpactStat label="AI responses sent" value={data.ai_impact.ai_responses} />
                <AiImpactStat
                  label="Estimated work saved"
                  value={`≈${data.ai_impact.estimated_hours_saved}h`}
                  hint="Rough estimate, not a measured benchmark"
                />
              </div>
            </CardContent>
          </Card>

          <div>
            <h2 className="mb-3 text-sm font-medium text-muted-foreground">Trends</h2>
            <div className="grid gap-4 lg:grid-cols-2">
              <Card interactive>
                <CardHeader>
                  <CardTitle className="text-base">Conversations over time</CardTitle>
                </CardHeader>
                <CardContent>
                  <TrendChart title="Conversations over time" data={data.trends.conversations} />
                </CardContent>
              </Card>
              <Card interactive>
                <CardHeader>
                  <CardTitle className="text-base">Messages over time</CardTitle>
                </CardHeader>
                <CardContent>
                  <TrendChart title="Messages over time" data={data.trends.messages} />
                </CardContent>
              </Card>
              <Card interactive>
                <CardHeader>
                  <CardTitle className="text-base">Leads over time</CardTitle>
                </CardHeader>
                <CardContent>
                  <TrendChart title="Leads over time" data={data.trends.leads} />
                </CardContent>
              </Card>
              <Card interactive>
                <CardHeader>
                  <CardTitle className="text-base">Appointments over time</CardTitle>
                </CardHeader>
                <CardContent>
                  <TrendChart title="Appointments over time" data={data.trends.appointments} />
                </CardContent>
              </Card>
            </div>
          </div>

          <div>
            <h2 className="mb-3 text-sm font-medium text-muted-foreground">Breakdowns</h2>
            <div className="grid gap-4 lg:grid-cols-3">
              <Card interactive>
                <CardHeader>
                  <CardTitle className="text-base">Conversations by status</CardTitle>
                </CardHeader>
                <CardContent>
                  <BreakdownList
                    entries={Object.entries(data.business_health.conversations_by_status)}
                    labelFor={(key) =>
                      CONVERSATION_STATUS_BADGE[key as Conversation["status"]]?.label ?? key
                    }
                  />
                </CardContent>
              </Card>
              <Card interactive>
                <CardHeader>
                  <CardTitle className="text-base">Leads by stage</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
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
                </CardContent>
              </Card>
              <Card interactive>
                <CardHeader>
                  <CardTitle className="text-base">Appointments by status</CardTitle>
                </CardHeader>
                <CardContent>
                  <BreakdownList
                    entries={Object.entries(data.business_health.appointments_by_status)}
                    labelFor={(key) =>
                      APPOINTMENT_STATUS_BADGE[key as Appointment["status"]]?.label ?? key
                    }
                  />
                </CardContent>
              </Card>
            </div>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">AI Performance</CardTitle>
            </CardHeader>
            <CardContent>
              <AiMetricsSummary data={data.ai_performance} isPending={false} isError={false} />
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}

function AiImpactStat({
  label,
  value,
  hint,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
}) {
  return (
    <div>
      <div className="font-mono text-xl font-semibold tabular-nums tracking-tight">{value}</div>
      <div className="mt-0.5 text-xs text-muted-foreground">{label}</div>
      {hint && <div className="mt-0.5 text-[10px] text-muted-foreground/70">{hint}</div>}
    </div>
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
    <ul className="space-y-2">
      {entries.map(([key, count]) => (
        <li key={key} className="space-y-1">
          <div className="flex items-center justify-between text-sm">
            <span className="capitalize">{labelFor ? labelFor(key) : key}</span>
            <span className="tabular-nums text-muted-foreground">{count}</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${max > 0 ? (count / max) * 100 : 0}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
