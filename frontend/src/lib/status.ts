// Canonical Badge-variant -> StatusPill-state translation (IMPLEMENTATION-
// ROADMAP-001 M15A, Status Consistency Sweep). Every conversion since M6 had
// independently re-derived this same mapping (success->success,
// warning->waiting, secondary/outline->idle, destructive->error) — this is
// the one place it's defined now, so a status's color can't drift between
// screens depending on which one happened to convert it first.
import type { ActivityState } from "@/components/ui/activity-dot";

export const VARIANT_TO_STATE: Record<
  "success" | "warning" | "secondary" | "destructive" | "outline",
  ActivityState
> = {
  success: "success",
  warning: "waiting",
  secondary: "idle",
  outline: "idle",
  destructive: "error",
};
