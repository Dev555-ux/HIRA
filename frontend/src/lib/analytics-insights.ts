import type { ActivityState } from "@/components/ui/activity-dot";
import { VARIANT_TO_STATE } from "@/lib/status";
import type {
  AnalyticsAiImpact,
  AnalyticsDashboard,
  AnalyticsOverview,
  AnalyticsTrendPoint,
} from "@/lib/types";
import { describeOnboardingStatus, describeWhatsAppConnection } from "@/lib/utils";

const DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

// The API returns exactly one range's daily series — no prior-period
// baseline exists anywhere in the payload. This compares the back half of
// the fetched window against the front half, which is honest about what it
// is (movement within this period), not a claim about "vs last week".
export function periodTrendPct(points: AnalyticsTrendPoint[]): number | null {
  if (points.length < 4) return null; // too few points for a half-split to mean anything
  const mid = Math.floor(points.length / 2);
  const firstSum = points.slice(0, mid).reduce((sum, p) => sum + p.count, 0);
  const secondSum = points.slice(mid).reduce((sum, p) => sum + p.count, 0);
  if (firstSum === 0) return null;
  return Math.round(((secondSum - firstSum) / firstSum) * 100);
}

// Which day of week the series peaked on, averaged across however many
// occurrences of that weekday fall in the range (so a 30d/90d range doesn't
// just report whichever single day happened to be highest).
export function dayOfWeekPeak(points: AnalyticsTrendPoint[]): string | null {
  if (points.length === 0) return null;
  const sums = new Array(7).fill(0) as number[];
  const counts = new Array(7).fill(0) as number[];
  for (const p of points) {
    const dow = new Date(`${p.date}T00:00:00Z`).getUTCDay();
    sums[dow] += p.count;
    counts[dow] += 1;
  }
  let best = -1;
  let bestAvg = 0;
  for (let i = 0; i < 7; i++) {
    if (counts[i] === 0) continue;
    const avg = sums[i] / counts[i];
    if (avg > bestAvg) {
      bestAvg = avg;
      best = i;
    }
  }
  return best === -1 ? null : DAY_NAMES[best];
}

// Sprint 85 — the "% of conversations AI handled without a human" figure was
// independently computed in both ExecutiveSummary and AiInsightsCard with the
// identical formula. Centralized here so it can't drift between the two, and
// so any future consumer (the Executive Health Score strip, KPI cards) reads
// the same number.
export function aiCoveragePct(overview: AnalyticsOverview, aiImpact: AnalyticsAiImpact): number | null {
  if (overview.total_conversations === 0) return null;
  return Math.round((aiImpact.conversations_handled / overview.total_conversations) * 100);
}

// The "% of AI responses grounded in the Knowledge Base" figure — previously
// only computed inline inside AiInsightsCard.
export function kbGroundedPct(aiImpact: AnalyticsAiImpact): number | null {
  if (aiImpact.ai_responses === 0) return null;
  return Math.round((aiImpact.kb_grounded_replies / aiImpact.ai_responses) * 100);
}

export interface HealthSignal {
  key: string;
  label: string;
  state: ActivityState;
}

// Thresholds for the two signals below that aren't a direct pass/fail on a
// real alert — named here so they're easy to find and revisit, not buried
// inline. Not a claim about what's "correct," just where the codebase draws
// the line today.
const SLOW_RESPONSE_SECONDS = 600; // 10 minutes
const ELEVATED_ESCALATION_RATIO = 0.25;

// Every signal in the Executive Health Score strip (Sprint 85), derived only
// from fields already present on AnalyticsDashboard — no new data, no LLM
// call, no fabricated metric. Reuses the same alert set and status-describing
// helpers Business Health / Home already use, so a business's status can't
// disagree between the two surfaces.
export function healthSignals(data: AnalyticsDashboard): HealthSignal[] {
  const { overview, business_health, ai_impact } = data;
  const whatsapp = describeWhatsAppConnection(business_health.whatsapp.status);
  const onboarding = describeOnboardingStatus(business_health.onboarding_status);

  const escalationRatio =
    overview.total_conversations > 0 ? ai_impact.human_escalations / overview.total_conversations : null;
  const escalationsElevated = escalationRatio !== null && escalationRatio > ELEVATED_ESCALATION_RATIO;

  const aiReliable = !business_health.alerts.includes("ai_failures") && overview.failed_responses_today === 0;
  const responseSlow =
    overview.avg_response_time_seconds !== null && overview.avg_response_time_seconds > SLOW_RESPONSE_SECONDS;
  const kbEmpty = business_health.alerts.includes("missing_knowledge_base");

  return [
    {
      key: "onboarding",
      label: onboarding.variant === "success" ? "Onboarding Live" : "Onboarding In Progress",
      state: VARIANT_TO_STATE[onboarding.variant],
    },
    {
      key: "whatsapp",
      label: `WhatsApp ${whatsapp.label}`,
      state: VARIANT_TO_STATE[whatsapp.variant],
    },
    {
      key: "knowledge_base",
      label: kbEmpty ? "Knowledge Base Empty" : "Knowledge Base Healthy",
      state: kbEmpty ? "waiting" : "success",
    },
    {
      key: "ai_reliability",
      label: aiReliable ? "AI Operating Normally" : "AI Failures Today",
      state: aiReliable ? "success" : "error",
    },
    {
      key: "escalations",
      label:
        escalationRatio === null
          ? "No Escalations Yet"
          : escalationsElevated
            ? "Escalations Elevated"
            : "Escalations Normal",
      state: escalationRatio === null ? "idle" : escalationsElevated ? "waiting" : "success",
    },
    {
      key: "response_health",
      label:
        overview.failed_responses_today > 0
          ? "Responses Failing"
          : responseSlow
            ? "Responses Slow"
            : "Response Health Good",
      state: overview.failed_responses_today > 0 ? "error" : responseSlow ? "waiting" : "success",
    },
  ];
}
