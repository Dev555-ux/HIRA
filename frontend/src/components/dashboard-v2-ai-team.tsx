import { AlertTriangle, BookOpen, Clock } from "lucide-react";
import Link from "next/link";
import { roleLabel } from "@/components/ai-metrics-section";
import { AIAvatar } from "@/components/ui/ai-avatar";
import { MemoryBadge } from "@/components/ui/memory-badge";
import type { RosterEntry } from "@/components/dashboard-v2-hero";
import { formatDuration } from "@/lib/utils";

// Dashboard V2's AI Workspace — a real team roster instead of a stat list.
// Every row is `RosterEntry` data the page derived from `ai_performance.
// employee_utilisation` (real 30-day turn counts per role); the proportion
// bar is that role's real share of total turns, not a fabricated "capacity"
// or "confidence" score — no such field exists on FounderAiMetrics, so
// none is shown (same "omit rather than invent" rule V1's Recent Leads
// already follows for AI recommendation/confidence).
export function AiTeamPanel({
  roster,
  avgResponseSeconds,
  escalations,
  kbPublished,
  learnedTodayCount,
}: {
  roster: RosterEntry[];
  avgResponseSeconds: number | null;
  escalations: number;
  kbPublished: number;
  learnedTodayCount: number;
}) {
  return (
    <div className="flex h-full flex-col rounded-2xl bg-card p-6 shadow-e2 sm:p-7">
      <div className="mb-5 flex items-center justify-between">
        <h2 className="type-title">AI workspace</h2>
        <span className="text-xs text-muted-foreground">Last 30 days</span>
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
          <span className="text-sm font-semibold">{formatDuration(avgResponseSeconds)}</span>
        </div>
        <div className="flex items-center justify-between gap-3 py-1.5">
          <span className="flex items-center gap-2 text-sm text-muted-foreground">
            <AlertTriangle className={escalations > 0 ? "size-3.5 text-warning" : "size-3.5"} aria-hidden="true" />
            Escalated to a human
          </span>
          <span className={escalations > 0 ? "text-sm font-semibold text-warning" : "text-sm font-semibold"}>
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
            <span className="text-sm font-semibold">{kbPublished} published</span>
            {learnedTodayCount > 0 && <MemoryBadge>+{learnedTodayCount} today</MemoryBadge>}
          </span>
        </div>
      </div>
    </div>
  );
}
