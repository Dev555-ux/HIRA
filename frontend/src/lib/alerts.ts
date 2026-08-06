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
