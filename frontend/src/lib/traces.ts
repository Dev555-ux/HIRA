// Shared trace-outcome state mapping — single source of truth for the trace
// list (app/(ops)/ops/traces/page.tsx) and the trace detail pane
// (components/trace-detail.tsx), so the two can't drift.
import type { ActivityState } from "@/components/ui/activity-dot";
import type { TraceOutcome } from "@/lib/types";

// IMPLEMENTATION-ROADMAP-001 M9: StatusPill's outcome->dot-color mapping,
// preserving the exact color grouping the old OUTCOME_BADGE variants had in
// both files: sent=success, pending_approval/escalated=warning,
// sending/no_result=secondary, failed/rejected=destructive.
export const TRACE_OUTCOME_STATE: Record<TraceOutcome, ActivityState> = {
  sent: "success",
  pending_approval: "waiting",
  sending: "idle",
  failed: "error",
  rejected: "error",
  escalated: "waiting",
  no_result: "idle",
};
