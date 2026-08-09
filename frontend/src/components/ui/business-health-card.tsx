import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusPill } from "@/components/ui/status-pill";
import { ALERT_LABEL } from "@/lib/alerts";
import { VARIANT_TO_STATE } from "@/lib/status";
import type { AnalyticsBusinessHealth } from "@/lib/types";
import { describeOnboardingStatus, describeWhatsAppConnection } from "@/lib/utils";

// Extracted from analytics/page.tsx (HIRA v2 Phase 1) — same component, same
// data contract, same rendered output; moved here so Home and any future
// screen can show it without duplicating the markup. Deliberately not a
// composite "score" — the real signal is which of these four things (WhatsApp,
// onboarding, knowledge base, alerts) needs attention, not a single number
// that would hide which one.
export function BusinessHealthCard({ health }: { health: AnalyticsBusinessHealth }) {
  const whatsapp = describeWhatsAppConnection(health.whatsapp.status);
  const onboarding = describeOnboardingStatus(health.onboarding_status);

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Business health</CardTitle>
        <StatusPill state={VARIANT_TO_STATE[whatsapp.variant]}>WhatsApp {whatsapp.label}</StatusPill>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
          <span className="flex items-center gap-1.5">
            Onboarding ·{" "}
            <StatusPill state={VARIANT_TO_STATE[onboarding.variant]}>{onboarding.label}</StatusPill>
          </span>
          <span>
            Knowledge base · {health.knowledge_base.published_count} published
            {health.knowledge_base.draft_count > 0 && `, ${health.knowledge_base.draft_count} draft`}
          </span>
          <span>
            {health.alerts.length === 0
              ? "No alerts"
              : health.alerts.map((a) => ALERT_LABEL[a]).join(" · ")}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
