import { Bot, Wrench } from "lucide-react";
import { roleLabel } from "@/components/ai-metrics-section";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusPill } from "@/components/ui/status-pill";
import type { FounderAiMetrics } from "@/lib/types";

// AI Performance (Sprint 85 redesign) — Analytics-only. Deliberately a
// separate component from AiMetricsSummary (components/ai-metrics-section.tsx),
// which stays untouched: that component is also rendered by the internal
// Founder Ops dashboard (app/(ops)/ops/page.tsx), and this redesign is scoped
// to the business owner's Analytics page only. Same FounderAiMetrics shape,
// same real fields — grouped as Reliability / Execution / AI Employees / Tool
// Usage / Failures instead of a flat StatCard grid, so a founder can tell
// whether the AI workforce is operating well without reading raw ms/step
// counts. The "operating normally" read is a real threshold on the two real
// failure counters below — not a fabricated score.
export function AiPerformanceCard({ data }: { data: FounderAiMetrics }) {
  if (data.total_turns === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">AI Performance</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No AI turns recorded yet — this fills in once customers start messaging.
          </p>
        </CardContent>
      </Card>
    );
  }

  const healthy = data.failed_tool_executions === 0 && data.governance_blocks === 0;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">AI Performance</CardTitle>
        <StatusPill state={healthy ? "success" : "waiting"}>
          {healthy ? "Operating normally" : "Needs a look"}
        </StatusPill>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-6 sm:grid-cols-3">
          <div>
            <p className="mb-2.5 type-caption font-semibold uppercase tracking-wide text-muted-foreground">
              AI Employees
            </p>
            <div className="flex items-center gap-2.5">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10">
                <Bot className="size-4 text-primary" aria-hidden="true" />
              </span>
              <div>
                <p className="text-lg font-semibold tracking-tight">
                  {data.most_used_employee ? roleLabel(data.most_used_employee) : "—"}
                </p>
                <p className="text-xs text-muted-foreground">Most active this period</p>
              </div>
            </div>
          </div>

          <div>
            <p className="mb-2.5 type-caption font-semibold uppercase tracking-wide text-muted-foreground">
              Execution
            </p>
            <div className="flex gap-5">
              <div>
                <p className="font-mono text-lg font-semibold tabular-nums">{data.total_turns}</p>
                <p className="text-xs text-muted-foreground">Turns traced</p>
              </div>
              <div>
                <p className="font-mono text-lg font-semibold tabular-nums">{data.avg_plan_length.toFixed(1)}</p>
                <p className="text-xs text-muted-foreground">Steps / turn</p>
              </div>
              <div>
                <p className="font-mono text-lg font-semibold tabular-nums">{Math.round(data.avg_execution_time_ms)}ms</p>
                <p className="text-xs text-muted-foreground">Avg execution</p>
              </div>
            </div>
          </div>

          <div>
            <p className="mb-2.5 type-caption font-semibold uppercase tracking-wide text-muted-foreground">
              Reliability
            </p>
            <div className="flex items-center justify-between gap-2 text-sm">
              <span>Plans stopped early (governance/readiness)</span>
              <Badge variant={data.governance_blocks > 0 ? "warning" : "secondary"}>{data.governance_blocks}</Badge>
            </div>
          </div>
        </div>

        <div className="grid gap-6 border-t pt-5 sm:grid-cols-2">
          <div>
            <p className="mb-2 type-caption font-semibold uppercase tracking-wide text-muted-foreground">
              Tool Usage
            </p>
            {data.most_used_tools.length === 0 ? (
              <p className="text-sm text-muted-foreground">No tool calls yet.</p>
            ) : (
              <ul className="space-y-1.5">
                {data.most_used_tools.map((tool) => (
                  <li key={tool.tool_name} className="flex items-center justify-between gap-2 text-sm">
                    <span className="flex items-center gap-1.5 text-muted-foreground">
                      <Wrench className="size-3.5" aria-hidden="true" />
                      {tool.tool_name}
                    </span>
                    <span className="tabular-nums text-muted-foreground">{tool.count}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <p className="mb-2 type-caption font-semibold uppercase tracking-wide text-muted-foreground">
              Failures
            </p>
            <div className="flex items-center justify-between gap-2 text-sm">
              <span>Failed tool executions</span>
              <Badge variant={data.failed_tool_executions > 0 ? "destructive" : "secondary"}>
                {data.failed_tool_executions}
              </Badge>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
