// Shared business-alert display labels — single source of truth for Founder
// Ops (app/(ops)/ops/page.tsx) and Analytics (app/(dashboard)/analytics/
// page.tsx), both of which render the same backend-computed alert set
// (app/services/analytics.py's business_alerts()), just cross-tenant vs.
// business-scoped.
import type { FounderAlert } from "@/lib/types";

export const ALERT_LABEL: Record<FounderAlert, string> = {
  whatsapp_disconnected: "WhatsApp disconnected",
  missing_knowledge_base: "No Knowledge Base",
  ai_failures: "AI failures",
  no_recent_activity: "No recent activity",
};

// Where each alert actually gets fixed — same alert set business_health
// already computes, just pointed at a real route each time instead of only
// being displayed as a badge. Sprint 85: originated in
// analytics-executive-summary.tsx; moved here (Sprint 86) once Dashboard's
// Needs Attention needed the same mapping — single source rather than two
// copies that could drift.
export const ALERT_HREF: Record<FounderAlert, string> = {
  whatsapp_disconnected: "/connect-whatsapp",
  missing_knowledge_base: "/knowledge-base",
  ai_failures: "#ai-performance",
  no_recent_activity: "/inbox",
};
