import { aiSurfaceClassName } from "@/components/ui/ai-surface";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import type { AnalyticsAiImpact, AnalyticsRange } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ImpactMetric {
  key: string;
  label: string;
  value: number;
  tone: "neutral" | "warning";
}

// AI Impact (Sprint 85 redesign) — same seven real fields on
// AnalyticsAiImpact as before, presented as a bar row instead of a flat
// number grid. `human_escalations` gets the warning tone; every other metric
// is positive volume and shares the neutral foreground tone — so a founder
// can tell at a glance which bar is the one caution number among six
// positive ones, without reading every label. Estimated hours saved is a
// different unit (hours, not a count) and would be misleading on the same
// bar scale as the others, so it stays a separate callout in the header
// instead of a seventh bar.
export function AiImpactCard({ impact, range }: { impact: AnalyticsAiImpact; range: AnalyticsRange }) {
  const metrics: ImpactMetric[] = [
    { key: "handled", label: "Conversations handled", value: impact.conversations_handled, tone: "neutral" },
    { key: "escalations", label: "Escalated to a human", value: impact.human_escalations, tone: "warning" },
    { key: "leads", label: "Leads created", value: impact.leads_created, tone: "neutral" },
    { key: "appointments", label: "Appointments booked", value: impact.appointments_booked, tone: "neutral" },
    { key: "kb", label: "KB-grounded replies", value: impact.kb_grounded_replies, tone: "neutral" },
    { key: "responses", label: "AI responses sent", value: impact.ai_responses, tone: "neutral" },
  ];
  const max = Math.max(1, ...metrics.map((m) => m.value));

  return (
    <Card className={cn(aiSurfaceClassName, "shadow-e2")}>
      <CardHeader className="flex-row items-baseline justify-between space-y-0">
        <CardTitle className="text-base">AI Impact · last {range}</CardTitle>
        <span className="text-sm text-muted-foreground">
          <span className="font-mono font-semibold tabular-nums text-foreground">≈{impact.estimated_hours_saved}h</span>{" "}
          saved
        </span>
      </CardHeader>
      <div className="grid grid-cols-3 gap-x-3 gap-y-6 px-6 pb-6 sm:grid-cols-6">
        {metrics.map((m) => (
          <div key={m.key} className="flex flex-col items-center gap-2">
            <div className="flex h-24 w-full items-end justify-center" aria-hidden="true">
              <div
                className={cn("w-2.5 rounded-full transition-[height]", m.tone === "warning" ? "bg-warning" : "bg-foreground/75")}
                style={{ height: `${Math.max(6, (m.value / max) * 100)}%` }}
              />
            </div>
            <div className="text-center">
              <p className="font-mono text-lg font-semibold tabular-nums">{m.value}</p>
              <p className="mt-0.5 text-[11px] leading-tight text-muted-foreground">{m.label}</p>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
