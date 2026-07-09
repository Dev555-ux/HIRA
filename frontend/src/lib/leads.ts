// Shared lead-stage display metadata — single source of truth for the stage
// select (components/customer-detail.tsx), the Customers list's stage badge,
// and the Leads list/filter chips (Sprint 32), so all three can't drift.
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

export const STAGE_BADGE_VARIANT: Record<
  LeadStage,
  "secondary" | "warning" | "success" | "destructive" | "outline"
> = {
  new: "secondary",
  contacted: "outline",
  qualified: "warning",
  proposal_sent: "warning",
  negotiation: "warning",
  won: "success",
  lost: "destructive",
};
