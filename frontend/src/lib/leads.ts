// Shared lead-stage display metadata — single source of truth for the stage
// select (components/customer-detail.tsx), the Customers list's stage badge,
// and the Leads list/filter chips (Sprint 32), so all three can't drift.
import type { ActivityState } from "@/components/ui/activity-dot";
import type { LeadStage } from "@/lib/types";

export const LEAD_STAGES: { value: LeadStage; label: string }[] = [
  { value: "new", label: "New" },
  { value: "contacted", label: "Contacted" },
  { value: "qualified", label: "Qualified" },
  { value: "proposal_sent", label: "Proposal sent" },
  { value: "negotiation", label: "Negotiation" },
  { value: "won", label: "Won" },
  { value: "lost", label: "Lost" },
];

export const STAGE_LABEL: Record<LeadStage, string> = Object.fromEntries(
  LEAD_STAGES.map((s) => [s.value, s.label]),
) as Record<LeadStage, string>;

// IMPLEMENTATION-ROADMAP-001 M6: StatusPill's stage→dot-color mapping,
// resolving the milestone's own open question — ActivityState's five states
// (idle/working/waiting/success/error) turn out to stretch cleanly onto
// seven lead stages with zero loss of accessible meaning, because StatusPill
// always pairs its dot with the stage's own text label (never color alone);
// two stages sharing a dot color is fine when their labels still read
// distinctly. This mapping also exactly preserves the color grouping the
// old STAGE_BADGE_VARIANT (removed — StatusPill is now the only status-color
// source of truth) already had: new/contacted were both neutral variants,
// qualified/proposal_sent/negotiation were all "warning", won was "success",
// lost was "destructive". Nothing here changes which stages read as the same
// color as each other — only the component presenting that color changed.
export const STAGE_STATUS: Record<LeadStage, ActivityState> = {
  new: "idle",
  contacted: "idle",
  qualified: "waiting",
  proposal_sent: "waiting",
  negotiation: "waiting",
  won: "success",
  lost: "error",
};
