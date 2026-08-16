import { Activity, Bot, Clock, ListTree, Wrench } from "lucide-react";
import { StatCard } from "@/components/stat-card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { FounderAiMetrics } from "@/lib/types";

// Exported (not just `roleLabel` below) so a caller needing the full real
// roster — not just a one-off label lookup — has a single source for it
// too, rather than re-declaring these four keys a second place (Dashboard
// V2's AI network visualization: `Object.keys(ROLE_LABEL)`).
export const ROLE_LABEL: Record<string, string> = {
  receptionist: "Receptionist",
  scheduler: "Scheduler",
  sales_executive: "Sales Executive",
  bookkeeper: "Bookkeeper",
};

export function roleLabel(role: string): string {
  return ROLE_LABEL[role] ?? role;
}

// Extracted from Ops's AiMetricsSection (Sprint 76) so Analytics (M14) can
// render the identical ai_performance shape (byte-for-byte the same as
// FounderAiMetrics — both come from app/services/analytics.py's
// ai_metrics(), business-scoped vs. cross-tenant) without a second
// implementation. Purely presentational — data fetching stays with each
// caller, since Ops and Analytics use different hooks/gates.
export function AiMetricsSummary({
  data,
  isPending,
  isError,
}: {
  data: FounderAiMetrics | undefined;
  isPending: boolean;
  isError: boolean;
}) {
  if (isError) {
    return <p className="text-sm text-muted-foreground">Couldn&apos;t load AI metrics.</p>;
  }

  if (isPending || !data) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
    );
  }

  if (data.total_turns === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No AI turns recorded yet — this fills in once customers start messaging.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Turns traced" value={data.total_turns} icon={Activity} />
        <StatCard
          label="Most-used employee"
          value={data.most_used_employee ? roleLabel(data.most_used_employee) : "—"}
          icon={Bot}
        />
        <StatCard
          label="Avg plan length"
          value={data.avg_plan_length.toFixed(1)}
          icon={ListTree}
          hint="Steps per turn"
        />
        <StatCard
          label="Avg execution time"
          value={`${Math.round(data.avg_execution_time_ms)}ms`}
          icon={Clock}
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Most-used tools
          </p>
          {data.most_used_tools.length === 0 ? (
            <p className="text-sm text-muted-foreground">No tool calls yet.</p>
          ) : (
            <ul className="space-y-1.5">
              {data.most_used_tools.map((tool) => (
                <li
                  key={tool.tool_name}
                  className="flex items-center justify-between gap-2 text-sm"
                >
                  <span className="flex items-center gap-1.5">
                    <Wrench className="size-3.5 text-muted-foreground" />
                    {tool.tool_name}
                  </span>
                  <span className="tabular-nums text-muted-foreground">{tool.count}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Reliability
          </p>
          <ul className="space-y-1.5 text-sm">
            <li className="flex items-center justify-between gap-2">
              <span>Failed tool executions</span>
              <Badge variant={data.failed_tool_executions > 0 ? "destructive" : "secondary"}>
                {data.failed_tool_executions}
              </Badge>
            </li>
            <li className="flex items-center justify-between gap-2">
              <span>Plans stopped early (governance/readiness)</span>
              <Badge variant={data.governance_blocks > 0 ? "warning" : "secondary"}>
                {data.governance_blocks}
              </Badge>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
