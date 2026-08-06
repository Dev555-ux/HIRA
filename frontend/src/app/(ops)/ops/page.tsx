"use client";

import {
  Activity,
  AlertTriangle,
  Bot,
  Building2,
  Clock,
  ListTree,
  MessageCircle,
  MessagesSquare,
  RefreshCw,
  ShieldOff,
} from "lucide-react";
import Link from "next/link";
import { AiMetricsSummary } from "@/components/ai-metrics-section";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import type { ActivityState } from "@/components/ui/activity-dot";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusPill } from "@/components/ui/status-pill";
import { useFounderAiMetrics, useFounderOverview } from "@/hooks/use-founder-ops";
import { ApiError } from "@/lib/api";
import { ALERT_LABEL } from "@/lib/alerts";
import type { FounderBusinessRow } from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";

// IMPLEMENTATION-ROADMAP-001 M9: StatusPill's status->dot-color mapping,
// single consumer (this file). Preserves WHATSAPP_BADGE's exact colors:
// connected=success, pending_verification=warning, not_connected=secondary.
const WHATSAPP_STATUS_STATE: Record<FounderBusinessRow["whatsapp"]["status"], ActivityState> = {
  connected: "success",
  pending_verification: "waiting",
  not_connected: "idle",
};

const WHATSAPP_LABEL: Record<FounderBusinessRow["whatsapp"]["status"], string> = {
  connected: "Connected",
  pending_verification: "Needs attention",
  not_connected: "Not connected",
};

// Onboarding's label depends on two fields (onboarding_complete AND
// onboarding_status) but its color only ever depended on onboarding_complete
// — "Live" and "Setting up" were always the same secondary/grey. Preserved
// exactly: only "Complete" gets the success dot.
function onboardingState(b: FounderBusinessRow): ActivityState {
  return b.onboarding_complete ? "success" : "idle";
}

function onboardingLabel(b: FounderBusinessRow): string {
  if (b.onboarding_complete) return "Complete";
  return b.onboarding_status === "live" ? "Live" : "Setting up";
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  return `${Math.round(minutes / 60)}h`;
}

function relativeOrNever(iso: string | null): string {
  return iso ? formatRelativeTime(iso) : "Never";
}

export default function FounderOpsPage() {
  const { data, isPending, isError, error, refetch, isFetching } = useFounderOverview();

  if (isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-64" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError) {
    // A 404 here means "not on the founder allowlist" — the backend
    // deliberately doesn't distinguish that from "route doesn't exist"
    // (see documentation/API.md), so the frontend shouldn't either. No
    // "you're not authorized" message that would confirm this feature
    // exists to someone who stumbled onto the URL.
    if (error instanceof ApiError && error.status === 404) {
      return (
        <EmptyState
          icon={ShieldOff}
          title="Not found"
          description="This page doesn't exist."
        />
      );
    }
    return (
      <EmptyState
        icon={AlertTriangle}
        title="Couldn't load the dashboard"
        description="Something went wrong — please try again."
        action={
          <Button size="sm" onClick={() => refetch()} disabled={isFetching}>
            {isFetching ? "Retrying…" : "Retry"}
          </Button>
        }
      />
    );
  }

  if (!data) return null; // unreachable once isPending/isError are both false — narrows the type

  const { summary, businesses } = data;
  const flagged = businesses.filter((b) => b.alerts.length > 0);

  return (
    <>
      <PageHeader
        title="Founder Operations"
        description="Every business using HIRA, at a glance."
        action={
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className={isFetching ? "animate-spin" : ""} />
            Refresh
          </Button>
        }
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total businesses" value={summary.total_businesses} icon={Building2} />
        <StatCard label="Connected" value={summary.connected_businesses} icon={MessageCircle} />
        <StatCard label="Active (24h)" value={summary.active_businesses} icon={Activity} />
        <StatCard label="Messages today" value={summary.messages_today} icon={MessagesSquare} />
        <StatCard label="AI responses today" value={summary.ai_responses_today} icon={Bot} />
        <StatCard label="Errors today" value={summary.failed_responses_today} icon={AlertTriangle} />
        <StatCard
          label="Avg response time"
          value={formatDuration(summary.avg_response_time_seconds)}
          icon={Clock}
        />
      </div>

      <AiMetricsSection />

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Needs attention</CardTitle>
        </CardHeader>
        <CardContent>
          {flagged.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nothing flagged right now.</p>
          ) : (
            <ul className="divide-y">
              {flagged.map((b) => (
                <li key={b.id} className="flex flex-wrap items-center justify-between gap-2 py-3 first:pt-0 last:pb-0">
                  <span className="text-sm font-medium">{b.name}</span>
                  <div className="flex flex-wrap gap-1.5">
                    {b.alerts.map((alert) => (
                      <Badge key={alert} variant="destructive">
                        {ALERT_LABEL[alert]}
                      </Badge>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">All businesses ({businesses.length})</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          {businesses.length === 0 ? (
            <EmptyState
              icon={Building2}
              title="No businesses yet"
              description="Businesses will appear here once someone signs up."
              className="border-0 py-10"
            />
          ) : (
            <table className="w-full min-w-[900px] text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Business</th>
                  <th className="px-4 py-3 font-medium">Onboarding</th>
                  <th className="px-4 py-3 font-medium">WhatsApp</th>
                  <th className="px-4 py-3 font-medium">Knowledge Base</th>
                  <th className="px-4 py-3 font-medium">AI Activity</th>
                  <th className="px-4 py-3 font-medium">Last activity</th>
                  <th className="px-4 py-3 font-medium">Alerts</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {businesses.map((b) => (
                  <tr key={b.id}>
                    <td className="px-4 py-3 align-top">
                      <p className="font-medium">{b.name}</p>
                      <p className="text-xs text-muted-foreground">
                        Created {formatRelativeTime(b.created_at)}
                      </p>
                    </td>
                    <td className="px-4 py-3 align-top">
                      <StatusPill state={onboardingState(b)}>{onboardingLabel(b)}</StatusPill>
                    </td>
                    <td className="px-4 py-3 align-top">
                      <StatusPill state={WHATSAPP_STATUS_STATE[b.whatsapp.status]}>
                        {WHATSAPP_LABEL[b.whatsapp.status]}
                      </StatusPill>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {b.whatsapp.display_phone_number ?? "No number yet"}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Last inbound {relativeOrNever(b.whatsapp.last_inbound_at)}
                      </p>
                    </td>
                    <td className="px-4 py-3 align-top">
                      <p>
                        {b.knowledge_base.published_count} published
                        {b.knowledge_base.draft_count > 0 && (
                          <span className="text-muted-foreground">
                            {" "}
                            · {b.knowledge_base.draft_count} draft
                          </span>
                        )}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Updated {relativeOrNever(b.knowledge_base.last_updated_at)}
                      </p>
                    </td>
                    <td className="px-4 py-3 align-top">
                      <p>{b.ai_activity.conversations} conversations</p>
                      <p className="text-xs text-muted-foreground">
                        {b.ai_activity.ai_responses} replies
                        {b.ai_activity.failed_responses > 0 && (
                          <span className="text-destructive">
                            {" "}
                            · {b.ai_activity.failed_responses} failed
                          </span>
                        )}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Avg {formatDuration(b.ai_activity.avg_response_time_seconds)}
                      </p>
                    </td>
                    <td className="px-4 py-3 align-top text-muted-foreground">
                      {relativeOrNever(b.last_activity_at)}
                    </td>
                    <td className="px-4 py-3 align-top">
                      {b.alerts.length === 0 ? (
                        <span className="text-muted-foreground">—</span>
                      ) : (
                        <div className="flex flex-wrap gap-1">
                          {b.alerts.map((alert) => (
                            <Badge key={alert} variant="destructive" className="whitespace-nowrap">
                              {ALERT_LABEL[alert]}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </>
  );
}

// Sprint 76, Objective B: AI Employee observability tiles. Fetched
// separately from the overview above (its own loading/error state) so a
// problem computing AI metrics can never take down the rest of the
// dashboard, which has nothing to do with it. Rendering itself lives in
// AiMetricsSummary (M14) — shared with Analytics, which shows the same
// ai_performance shape business-scoped rather than cross-tenant.
function AiMetricsSection() {
  const { data, isPending, isError } = useFounderAiMetrics();

  return (
    <Card className="mb-6">
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle className="text-base">AI Employee Activity</CardTitle>
        <Button variant="outline" size="sm" asChild>
          <Link href="/ops/traces">
            <ListTree />
            View executions
          </Link>
        </Button>
      </CardHeader>
      <CardContent>
        <AiMetricsSummary data={data} isPending={isPending} isError={isError} />
      </CardContent>
    </Card>
  );
}
