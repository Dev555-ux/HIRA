import { AlertTriangle, Bot, BookOpen, Clock, Wrench } from "lucide-react";
import Link from "next/link";
import { roleLabel } from "@/components/ai-metrics-section";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MemoryBadge } from "@/components/ui/memory-badge";
import type { FounderAiMetrics } from "@/lib/types";
import { cn, formatDuration } from "@/lib/utils";

function Row({
  icon: Icon,
  label,
  value,
  tone = "neutral",
}: {
  icon: typeof Bot;
  label: string;
  value: React.ReactNode;
  tone?: "neutral" | "warning";
}) {
  return (
    <div className="flex items-center justify-between gap-3 py-2.5">
      <span className="flex min-w-0 items-center gap-2.5 text-sm text-muted-foreground">
        <Icon className={cn("size-4 shrink-0", tone === "warning" && "text-warning")} aria-hidden="true" />
        <span className="truncate">{label}</span>
      </span>
      <span className={cn("shrink-0 text-sm font-semibold", tone === "warning" && "text-warning")}>{value}</span>
    </div>
  );
}

// AI Workspace (Sprint 86) — a compact summary of what HIRA's been doing,
// distinct from "Needs your attention" (what to decide now) and "Recent
// activity" (a play-by-play log). Every figure here was already being
// fetched by the dashboard's existing useAnalyticsDashboard("30d") call —
// ai_performance (FounderAiMetrics) and overview.avg_response_time_seconds
// were both fetched but never rendered on Home before this. No new request,
// no fabricated metric.
export function AiWorkspaceCard({
  metrics,
  avgResponseSeconds,
  escalations,
  kbPublished,
  learnedTodayCount,
  className,
}: {
  metrics: FounderAiMetrics;
  avgResponseSeconds: number | null;
  /** Real 30-day escalation count (AnalyticsAiImpact.human_escalations) —
   *  deliberately not the live "open now" count, which already has its own
   *  home in Needs Attention; this one answers "how often," not "what's
   *  outstanding." */
  escalations: number;
  kbPublished: number;
  learnedTodayCount: number;
  className?: string;
}) {
  const topTool = metrics.most_used_tools[0]?.tool_name ?? null;

  return (
    <Card interactive className={cn("h-full shadow-e3", className)}>
      <CardHeader>
        <CardTitle className="text-base">AI workspace</CardTitle>
      </CardHeader>
      <CardContent className="divide-y">
        <Row
          icon={Bot}
          label="Most active employee"
          value={metrics.most_used_employee ? roleLabel(metrics.most_used_employee) : "—"}
        />
        <Row icon={Clock} label="Avg response time" value={formatDuration(avgResponseSeconds)} />
        <Row
          icon={AlertTriangle}
          label="Escalated to a human · 30d"
          value={escalations}
          tone={escalations > 0 ? "warning" : "neutral"}
        />
        <div className="flex items-center justify-between gap-3 py-2.5">
          <span className="flex min-w-0 items-center gap-2.5 text-sm text-muted-foreground">
            <BookOpen className="size-4 shrink-0" aria-hidden="true" />
            <Link href="/knowledge-base" className="truncate hover:text-foreground hover:underline">
              Knowledge base
            </Link>
          </span>
          <span className="flex shrink-0 items-center gap-2">
            <span className="text-sm font-semibold">{kbPublished} published</span>
            {learnedTodayCount > 0 && <MemoryBadge>+{learnedTodayCount} today</MemoryBadge>}
          </span>
        </div>
        {topTool && <Row icon={Wrench} label="Most used tool" value={<code className="font-mono">{topTool}</code>} />}
      </CardContent>
    </Card>
  );
}
