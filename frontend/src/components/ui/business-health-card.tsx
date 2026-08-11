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
//
// V6 (Home only — see `explain` below): leads with a plain-language
// explanation instead of asking the reader to interpret a status row —
// "explain, not merely report." The sentence is built entirely from
// `health.alerts`, the backend's own already-computed real issue list
// (business_alerts() in app/services/analytics.py) — never a second,
// re-derived notion of "issue," so this can't disagree with the alert row
// still shown below it for the specifics.
export function BusinessHealthCard({
  health,
  explain = false,
}: {
  health: AnalyticsBusinessHealth;
  /** Home's "explain, not merely report" sentence (V6). Analytics keeps its
   *  original status-row-only presentation — this redesign is scoped to
   *  Home, not Analytics, even though both render this shared component. */
  explain?: boolean;
}) {
  const whatsapp = describeWhatsAppConnection(health.whatsapp.status);
  const onboarding = describeOnboardingStatus(health.onboarding_status);
  const issues = health.alerts.map((a) => ALERT_LABEL[a]);

  const headline = issues.length === 0 ? "Excellent." : issues.length === 1 ? "Good." : "Needs a look.";
  const explanation =
    issues.length === 0
      ? "Your business is running normally."
      : issues.length === 1
        ? `Your business is running normally. The only issue today is ${issues[0].toLowerCase()}.`
        : `Your business is running normally. ${issues.length} things need a look: ${issues.join(", ")}.`;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Business health</CardTitle>
        <StatusPill state={VARIANT_TO_STATE[whatsapp.variant]}>WhatsApp {whatsapp.label}</StatusPill>
      </CardHeader>
      <CardContent className="space-y-4">
        {explain && (
          <p className="text-base">
            <span className="font-semibold">{headline}</span> {explanation}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
          <span className="flex items-center gap-1.5">
            Onboarding ·{" "}
            <StatusPill state={VARIANT_TO_STATE[onboarding.variant]}>{onboarding.label}</StatusPill>
          </span>
          <span>
            Knowledge base · {health.knowledge_base.published_count} published
            {health.knowledge_base.draft_count > 0 && `, ${health.knowledge_base.draft_count} draft`}
          </span>
          <span>{issues.length === 0 ? "No alerts" : issues.join(" · ")}</span>
        </div>
      </CardContent>
    </Card>
  );
}
