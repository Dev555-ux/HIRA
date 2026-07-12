// Shared conversation-status display metadata — single source of truth for
// the Inbox list (Sprint "Inbox") and the Dashboard's recent-conversations
// widget (Sprint 40), so the two can't drift.
import type { Conversation } from "@/lib/types";

export const CONVERSATION_STATUS_BADGE: Record<
  Conversation["status"],
  { label: string; variant: "secondary" | "warning" | "outline" }
> = {
  active: { label: "Open", variant: "secondary" },
  escalated: { label: "Escalated", variant: "warning" },
  closed: { label: "Closed", variant: "outline" },
};
