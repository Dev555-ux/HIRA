"use client";

import { AlertTriangle, CalendarClock, CheckCheck, Sparkles, UserPlus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo } from "react";
import Link from "next/link";
import { ActivityTimeline } from "@/components/dashboard-activity-timeline";
import { ROLE_LABEL } from "@/components/ai-metrics-section";
import { AiInsightsCard } from "@/components/analytics-ai-insights";
import { AiTeamPanel } from "@/components/dashboard-v2-ai-team";
import { AttentionQueue, type AttentionItem } from "@/components/dashboard-v2-attention-queue";
import { RecentCustomersPanel } from "@/components/dashboard-v2-customers";
import { RecentLeadsCard } from "@/components/dashboard-recent-leads";
import type { RosterEntry } from "@/components/dashboard-v2-hero";
import { DashboardV3Hero } from "@/components/dashboard-v3-hero";
import { SchedulePanel } from "@/components/dashboard-v2-schedule";
import { ExecutiveSummary } from "@/components/analytics-executive-summary";
import { OnboardingChecklist } from "@/components/onboarding-checklist";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendChart } from "@/components/ui/trend-chart";
import { useAiActivity } from "@/hooks/use-activity";
import { useAnalyticsDashboard } from "@/hooks/use-analytics";
import { useAppointments } from "@/hooks/use-appointments";
import { useCustomers } from "@/hooks/use-customers";
import { useAuthContext } from "@/lib/auth-context";
import { useEscalations } from "@/hooks/use-escalations";
import { useKbEntries } from "@/hooks/use-knowledge-base";
import { useLeads } from "@/hooks/use-leads";
import { useOnboardingStatus } from "@/hooks/use-onboarding";
import { usePending } from "@/hooks/use-pending";
import { ALERT_HREF, ALERT_LABEL } from "@/lib/alerts";
import { REASON_LABEL } from "@/lib/escalations";

const PREVIEW_ROWS = 5;
const ACTIVITY_ROWS = 6;
// Fetched larger than shown so Recent Customers can sort by real
// last_message_at client-side — see dashboard-v2/page.tsx's original
// comment; same reasoning, unchanged here.
const CUSTOMER_FETCH = 20;
const CUSTOMER_ROWS = 5;

function customerLabel(customer: { display_name: string | null; wa_phone: string | null } | null): string {
  return customer?.display_name || customer?.wa_phone || "Unknown customer";
}

function pluralize(count: number, singular: string, plural: string): string {
  return count === 1 ? singular : plural;
}

function isToday(iso: string): boolean {
  const d = new Date(iso);
  const now = new Date();
  return (
    d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate()
  );
}

// A hairline-plus-label section kicker — the only wayfinding device between
// zones that don't already carry their own heading (Operations/People/
// Insights are Sprint 89 groupings over existing panels, not new
// components). Deliberately not a full divider: a label the eye can skip
// past, not a rule that interrupts the scroll.
function SectionKicker({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-5 flex items-center gap-3">
      <h2 className="type-caption shrink-0 font-semibold uppercase tracking-widest text-muted-foreground">
        {children}
      </h2>
      <div className="h-px flex-1 bg-border/60" aria-hidden="true" />
    </div>
  );
}

// Dashboard V3 — Sprint 88 built the composition (V2's real functionality,
// V1's visual language, no invented data). Sprint 89 is a founder-polish
// pass on top: no new data, no new components, only removal and
// refinement. Two more sections cut this round, on the same "does this
// deserve to exist" test Sprint 88 used to cut Performance Metrics and
// Learned Today:
//  - AskHiraBar: a full-weight card duplicating the global ⌘K command
//    palette (its own onClick literally just dispatches the same keyboard
//    event AppShell's listener already handles — see ask-hira-bar.tsx). It
//    sat directly under the hero, breaking the Hero → Executive Summary
//    read the founder brief asks for, for a capability that's one keystroke
//    away from every screen already.
//  - Quick actions: every link in it (Demo Chat, Pending Replies, Business
//    Knowledge, Calendar) already lives in the persistent sidebar (see
//    lib/nav.ts) and the "Test AI" / "Review replies" hero actions cover
//    the two that matter most in the moment. A footer of duplicate nav
//    links doesn't earn a place on an executive dashboard.
export default function DashboardV3Page() {
  const { user } = useAuthContext();
  const router = useRouter();

  const { data: pending, isFetching: isFetchingPending, refetch: refetchPending } = usePending();
  const { data: onboarding, isFetching: isFetchingOnboarding, refetch: refetchOnboarding } =
    useOnboardingStatus();
  const {
    data: aiActivityResult,
    isPending: isLoadingActivity,
    isFetching: isFetchingActivity,
    isError: isActivityError,
    refetch: refetchActivity,
  } = useAiActivity(ACTIVITY_ROWS);
  const {
    data: recentLeadsPage,
    isFetching: isFetchingLeads,
    refetch: refetchLeads,
  } = useLeads({ limit: PREVIEW_ROWS });
  const now = useMemo(() => new Date().toISOString(), []);
  const { data: upcomingAppointmentsResult, isFetching: isFetchingAppointments, refetch: refetchAppointments } =
    useAppointments({ from: now });
  const { data: openEscalationsResult, isFetching: isFetchingEscalations, refetch: refetchEscalations } =
    useEscalations({ status: "open", limit: PREVIEW_ROWS });
  const {
    data: analyticsDashboard,
    isFetching: isFetchingAnalytics,
    refetch: refetchAnalytics,
  } = useAnalyticsDashboard("30d");
  const { data: kbEntries, isFetching: isFetchingKb, refetch: refetchKb } = useKbEntries();
  const { data: customersPage, isFetching: isFetchingCustomers, refetch: refetchCustomers } = useCustomers({
    limit: CUSTOMER_FETCH,
  });

  const upcomingAppointments = useMemo(() => upcomingAppointmentsResult ?? [], [upcomingAppointmentsResult]);
  const aiActivity = useMemo(() => aiActivityResult ?? [], [aiActivityResult]);
  const openEscalations = useMemo(() => openEscalationsResult?.data ?? [], [openEscalationsResult]);
  const recentLeads = useMemo(() => recentLeadsPage?.data ?? [], [recentLeadsPage]);
  const customers = useMemo(() => {
    const all = customersPage?.data ?? [];
    return [...all]
      .sort((a, b) => {
        if (!a.last_message_at && !b.last_message_at) return 0;
        if (!a.last_message_at) return 1;
        if (!b.last_message_at) return -1;
        return new Date(b.last_message_at).getTime() - new Date(a.last_message_at).getTime();
      })
      .slice(0, CUSTOMER_ROWS);
  }, [customersPage]);
  const learnedToday = useMemo(
    () => (kbEntries ?? []).filter((entry) => isToday(entry.created_at)),
    [kbEntries],
  );
  const healthAlerts = useMemo(
    () => analyticsDashboard?.business_health.alerts ?? [],
    [analyticsDashboard],
  );

  const totalTurns = analyticsDashboard?.ai_performance.total_turns ?? 0;
  const roster = useMemo<RosterEntry[]>(() => {
    const utilisation = analyticsDashboard?.ai_performance.employee_utilisation ?? {};
    return Object.keys(ROLE_LABEL)
      .map((role) => {
        const count = utilisation[role] ?? 0;
        return {
          role,
          count,
          pct: totalTurns > 0 ? Math.round((count / totalTurns) * 100) : 0,
          mostActive: role === analyticsDashboard?.ai_performance.most_used_employee,
          active: count > 0,
        };
      })
      .sort((a, b) => b.count - a.count);
  }, [analyticsDashboard, totalTurns]);
  const activeRoster = useMemo(() => roster.filter((r) => r.active), [roster]);

  const pendingCount = pending?.length ?? 0;
  const escalationCount = openEscalations.length;

  const repliesToday = analyticsDashboard?.overview.ai_responses_today ?? 0;
  const appointmentsBookedToday = useMemo(
    () => upcomingAppointments.filter((a) => isToday(a.created_at)).length,
    [upcomingAppointments],
  );
  const leadsToday = useMemo(() => recentLeads.filter((l) => isToday(l.created_at)).length, [recentLeads]);
  const escalationsToday = useMemo(
    () => openEscalations.filter((e) => isToday(e.created_at)).length,
    [openEscalations],
  );

  const highlights = useMemo(() => {
    const items: { icon: typeof CheckCheck; label: string }[] = [];
    if (repliesToday > 0) {
      items.push({ icon: CheckCheck, label: `${repliesToday} customer ${pluralize(repliesToday, "message", "messages")} handled` });
    }
    if (appointmentsBookedToday > 0) {
      items.push({
        icon: CalendarClock,
        label: `${appointmentsBookedToday} ${pluralize(appointmentsBookedToday, "appointment", "appointments")} booked`,
      });
    }
    if (leadsToday > 0) {
      items.push({ icon: UserPlus, label: `${leadsToday} new ${pluralize(leadsToday, "lead", "leads")}` });
    }
    if (escalationsToday > 0) {
      items.push({
        icon: AlertTriangle,
        label: `${escalationsToday} ${pluralize(escalationsToday, "conversation", "conversations")} escalated`,
      });
    }
    return items;
  }, [repliesToday, appointmentsBookedToday, leadsToday, escalationsToday]);

  const attentionEmpty = pendingCount === 0 && escalationCount === 0 && healthAlerts.length === 0;
  const summary = "Here's what's happening with your business.";

  const hubState = healthAlerts.some((a) => a === "whatsapp_disconnected" || a === "ai_failures")
    ? "error"
    : healthAlerts.length > 0
      ? "waiting"
      : "success";

  const attentionItems = useMemo<AttentionItem[]>(() => {
    const items: AttentionItem[] = [];
    for (const p of pending ?? []) {
      items.push({
        id: `pending-${p.id}`,
        priority: "medium",
        title: customerLabel(p.customer),
        reason: "Reply drafted — waiting for your approval",
        actionLabel: "Review",
        createdAt: p.created_at,
        onAction: () => router.push("/pending"),
      });
    }
    for (const e of openEscalations) {
      items.push({
        id: `escalation-${e.id}`,
        priority: "high",
        title: customerLabel(e.conversation.customer),
        reason: REASON_LABEL[e.reason],
        actionLabel: "Review",
        createdAt: e.created_at,
        onAction: () => router.push("/escalations"),
      });
    }
    for (const alert of healthAlerts) {
      items.push({
        id: `alert-${alert}`,
        priority: alert === "whatsapp_disconnected" || alert === "ai_failures" ? "high" : "medium",
        title: ALERT_LABEL[alert],
        reason: "Business health",
        actionLabel: "Fix",
        createdAt: analyticsDashboard?.business_health.created_at ?? new Date().toISOString(),
        onAction: () => router.push(ALERT_HREF[alert]),
      });
    }
    return items.sort((a, b) => (a.priority === b.priority ? 0 : a.priority === "high" ? -1 : 1));
  }, [pending, openEscalations, healthAlerts, analyticsDashboard, router]);

  const isRefreshing =
    isFetchingPending ||
    isFetchingOnboarding ||
    isFetchingActivity ||
    isFetchingLeads ||
    isFetchingAppointments ||
    isFetchingEscalations ||
    isFetchingAnalytics ||
    isFetchingKb ||
    isFetchingCustomers;

  function refreshAll() {
    refetchPending();
    refetchOnboarding();
    refetchActivity();
    refetchLeads();
    refetchAppointments();
    refetchEscalations();
    refetchAnalytics();
    refetchKb();
    refetchCustomers();
  }

  return (
    <>
      <DashboardV3Hero
        name={user?.name ?? "there"}
        summary={summary}
        highlights={highlights}
        needsAttention={!attentionEmpty}
        isRefreshing={isRefreshing}
        onRefresh={refreshAll}
        pendingCount={pendingCount}
        roster={roster}
        hubState={hubState}
        healthData={analyticsDashboard}
      />

      {onboarding?.business && onboarding.business.onboarding_status !== "live" && (
        <OnboardingChecklist business={onboarding.business} />
      )}

      {/* Executive Summary — the page's one home for headline KPIs
          (conversations + trend, what needs attention, work saved). Real
          numbers, computed once from analyticsDashboard; never repeated as
          a separate stat strip elsewhere on this page. */}
      {analyticsDashboard && (
        <div className="mb-14">
          <ExecutiveSummary data={analyticsDashboard} />
        </div>
      )}

      {/* Needs Attention (inbox) + AI Workspace (control panel) — asymmetric
          7/5, attention leading. Same merged-queue and roster-panel data as
          Sprint 88; each panel now reads by its own metaphor instead of two
          identical stat cards side by side. */}
      <div className="mb-14 grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <AttentionQueue items={attentionItems} variant="inbox" />
        </div>
        <div className="lg:col-span-5">
          <AiTeamPanel
            roster={activeRoster}
            totalTurns={totalTurns}
            avgResponseSeconds={analyticsDashboard?.overview.avg_response_time_seconds ?? null}
            escalations={analyticsDashboard?.ai_impact.human_escalations ?? 0}
            kbPublished={analyticsDashboard?.business_health.knowledge_base.published_count ?? 0}
            learnedTodayCount={learnedToday.length}
            variant="console"
          />
        </div>
      </div>

      {/* Conversation Trend — a presentation canvas, not another bordered
          card: flat gradient surface, no shadow competing with the panels
          above, the chart given the full width to be the page's second
          focal point after the hero. */}
      {analyticsDashboard && (
        <div className="mb-14 rounded-3xl bg-gradient-to-b from-card to-muted/20 p-8 sm:p-10">
          <div className="mb-6 flex items-baseline justify-between">
            <h2 className="type-heading">Conversation trend</h2>
            <span className="text-xs text-muted-foreground">Last 30 Days</span>
          </div>
          <TrendChart title="Conversations over time" data={analyticsDashboard.trends.conversations} variant="hero" />
        </div>
      )}

      {/* Operations — what's ahead, what already happened. */}
      <div className="mb-14">
        <SectionKicker>Operations</SectionKicker>
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <SchedulePanel appointments={upcomingAppointments} />
          </div>
          <div className="lg:col-span-7 rounded-2xl bg-card shadow-e2">
            <div className="flex items-center justify-between px-6 pt-6 sm:px-7 sm:pt-7">
              <h2 className="type-title">Recent activity</h2>
              <Button asChild size="sm" variant="ghost">
                <Link href="/inbox">View all</Link>
              </Button>
            </div>
            <div className="mt-2 pb-2">
              {isActivityError ? (
                <EmptyState
                  icon={AlertTriangle}
                  title="Couldn't load activity"
                  description="Something went wrong — please try again."
                  action={
                    <Button size="sm" onClick={() => refetchActivity()}>
                      Retry
                    </Button>
                  }
                  className="border-0 py-12"
                />
              ) : isLoadingActivity ? (
                <div className="space-y-3 px-6 py-4 sm:px-7">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-10 w-full" />
                  ))}
                </div>
              ) : aiActivity.length === 0 ? (
                <EmptyState
                  icon={Sparkles}
                  title="Waiting for your first customer"
                  description="HIRA is set up and listening — as soon as a customer messages you, replies, bookings, and conversations will start showing up here. Not ready to wait? Try it yourself in Demo Chat."
                  action={
                    <Button asChild size="sm" variant="outline">
                      <Link href="/demo">Try Demo Chat</Link>
                    </Button>
                  }
                  className="border-0 py-12"
                />
              ) : (
                <ActivityTimeline entries={aiActivity} />
              )}
            </div>
          </div>
        </div>
      </div>

      {/* People — who's on the other end. */}
      <div className="mb-14">
        <SectionKicker>People</SectionKicker>
        <div className="grid gap-6 lg:grid-cols-12">
          <RecentLeadsCard leads={recentLeads} className="lg:col-span-7" polished />
          <div className="lg:col-span-5">
            <RecentCustomersPanel customers={customers} variant="feed" />
          </div>
        </div>
      </div>

      {/* Insights — the page's closing, editorial read of the same period's
          data. V1's Analytics component reused as-is; it renders nothing
          itself once there's no conversation data yet, so the kicker is
          gated on the same condition rather than heading an empty section. */}
      {analyticsDashboard && analyticsDashboard.overview.total_conversations > 0 && (
        <div>
          <SectionKicker>Insights</SectionKicker>
          <AiInsightsCard data={analyticsDashboard} />
        </div>
      )}
    </>
  );
}
