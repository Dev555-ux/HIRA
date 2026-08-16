// Shared escalation-reason display labels. Originally local to
// app/(dashboard)/escalations/page.tsx (M8) — extracted here once Dashboard
// V2's Needs Attention queue became a second consumer, per that file's own
// "kept local rather than a new lib/escalations.ts [while there's a] single
// consumer" note.
import type { EscalationReason } from "@/lib/types";

export const REASON_LABEL: Record<EscalationReason, string> = {
  low_confidence: "AI wasn't confident",
  customer_request: "Customer asked for a human",
  external_failure: "Message failed to send",
  automation_failed: "Autonomous action couldn't complete",
  other: "Other",
};
