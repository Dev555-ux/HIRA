import { AlertTriangle, BookOpen, Clock } from "lucide-react";
import Link from "next/link";
import { roleLabel } from "@/components/ai-metrics-section";
import { AIAvatar } from "@/components/ui/ai-avatar";
import { MemoryBadge } from "@/components/ui/memory-badge";
import type { RosterEntry } from "@/components/dashboard-v2-hero";
import { cn, formatDuration } from "@/lib/utils";

// Dashboard V2's AI Workspace — a real team roster instead of a stat list.
// Every row is `RosterEntry` data the page derived from `ai_performance.
// employee_utilisation` (real 30-day turn counts per role); the proportion
// bar is that role's real share of total turns, not a fabricated "capacity"
// or "confidence" score — no such field exists on FounderAiMetrics, so
// none is shown (same "omit rather than invent" rule V1's Recent Leads
// already follows for AI recommendation/confidence).
//
// `variant="console"` (used by the production Dashboard — default "panel" keeps
// every existing caller byte-identical) leans the same data into a control-
// panel reading: a recessed inset surface instead of a flat card, a live
// status dot, tabular-numeric readouts. No new data, no new component.
export function AiTeamPanel({
  roster,
  totalTurns,
  avgResponseSeconds,
  escalations,
  kbPublished,
  learnedTodayCount,
  variant = "panel",
}: {
  /** Active roles only (count > 0) — a "0 turns" row here would be
   *  telemetry with no outcome, not useful list content. The hero's
   *  AiNetwork is the one place the *full*, always-4 roster belongs. */
  roster: RosterEntry[];
  /** Real ai_performance.total_turns — shown so each row's "%" has a
   *  visible denominator (Sprint 88: the bare percentages had no context
   *  for why they didn't sum to 100 — not every turn is attributed to one
   *  of the four named roles). */
  totalTurns: number;
  avgResponseSeconds: number | null;
  escalations: number;
  kbPublished: number;
  learnedTodayCount: number;
  variant?: "panel" | "console";
}) {
  const isConsole = variant === "console";

  return (
    <div
      className={cn(
        "flex h-full flex-col rounded-2xl p-6 sm:p-7",
        isConsole ? "bg-muted/30 shadow-e1 ring-1 ring-inset ring-border/60" : "bg-card shadow-e2",
      )}
    >
      <div className="mb-5 flex items-center justify-between">
        <h2 className={isConsole ? "type-caption font-semibold uppercase tracking-wide text-muted-foreground" : "type-title"}>
          AI workspace
        </h2>
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          {isConsole && totalTurns > 0 && (
            <span className="size-1.5 rounded-full bg-success animate-ambient-pulse" aria-hidden="true" />
          )}
          {totalTurns > 0 ? `${totalTurns} turns · Last 30 days` : "Last 30 days"}
        </span>
      </div>

      {roster.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No AI turns recorded yet — this fills in once customers start messaging.
        </p>
      ) : (
        <ul className="space-y-4">
          {roster.map((r) => (
            <li key={r.role} className="flex items-center gap-3">
              <AIAvatar name={roleLabel(r.role)} state={r.mostActive ? "success" : "idle"} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-medium">{roleLabel(r.role)}</span>
                  <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                    {r.count} turns · {r.pct}%
                  </span>
                </div>
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-brand transition-[width] duration-700 ease-out"
                    style={{ width: `${Math.max(4, r.pct)}%` }}
                  />
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* Shared team vitals — real system-wide signals (not per-employee,
          since none exist), same fields V1's AI Workspace card surfaced. */}
      <div className="mt-6 space-y-0.5 border-t pt-5">
        <div className="flex items-center justify-between gap-3 py-1.5">
          <span className="flex items-center gap-2 text-sm text-muted-foreground">
            <Clock className="size-3.5" aria-hidden="true" />
            Avg response time
          </span>
          <span className="text-sm font-semibold tabular-nums">{formatDuration(avgResponseSeconds)}</span>
        </div>
        <div className="flex items-center justify-between gap-3 py-1.5">
          <span className="flex items-center gap-2 text-sm text-muted-foreground">
            <AlertTriangle className={escalations > 0 ? "size-3.5 text-warning" : "size-3.5"} aria-hidden="true" />
            Escalated to a human
          </span>
          <span className={cn("text-sm font-semibold tabular-nums", escalations > 0 && "text-warning")}>
            {escalations}
          </span>
        </div>
        <div className="flex items-center justify-between gap-3 py-1.5">
          <span className="flex items-center gap-2 text-sm text-muted-foreground">
            <BookOpen className="size-3.5" aria-hidden="true" />
            <Link href="/knowledge-base" className="hover:text-foreground hover:underline">
              Knowledge base
            </Link>
          </span>
          <span className="flex items-center gap-2">
            <span className="text-sm font-semibold tabular-nums">{kbPublished} published</span>
            {learnedTodayCount > 0 && <MemoryBadge>+{learnedTodayCount} today</MemoryBadge>}
          </span>
        </div>
      </div>
    </div>
  );
}
