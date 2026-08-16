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
import { DashboardHero, type BriefHighlight } from "@/components/dashboard-hero";
import { SchedulePanel } from "@/components/dashboard-v2-schedule";
import { ExecutiveSummary } from "@/components/analytics-executive-summary";
import { OnboardingChecklist } from "@/components/onboarding-checklist";
import { ReviewReplyCard } from "@/components/review-reply-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { MemoryBadge } from "@/components/ui/memory-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendChart } from "@/components/ui/trend-chart";
import { useToast } from "@/components/ui/toast";
import { useAiActivity } from "@/hooks/use-activity";
import { useAnalyticsDashboard } from "@/hooks/use-analytics";
import { useAppointments } from "@/hooks/use-appointments";
import { useCustomers } from "@/hooks/use-customers";
import { useAuthContext } from "@/lib/auth-context";
import { useEscalations } from "@/hooks/use-escalations";
import { useKbEntries } from "@/hooks/use-knowledge-base";
import { useLeads } from "@/hooks/use-leads";
import { useOnboardingStatus } from "@/hooks/use-onboarding";
import { useApprove, usePending, useReject, useUpdateDraft } from "@/hooks/use-pending";
import { ALERT_HREF, ALERT_LABEL } from "@/lib/alerts";
import { REASON_LABEL } from "@/lib/escalations";
import type { PendingReply } from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";

const PREVIEW_ROWS = 5;
const ACTIVITY_ROWS = 6;
// Fetched larger than shown so Recent Customers can sort by real
// last_message_at client-side — the backend orders by created_at, which
// surfaced a customer who signed up recently but hadn't messaged in 50
// days as "recent" — not who matters today.
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
// Insights are groupings over existing panels, not new components).
// Deliberately not a full divider: a label the eye can skip past, not a
// rule that interrupts the scroll.
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

// The production Dashboard — promoted from Dashboard V3 (Sprint 91), which
// itself combined V2's real functionality with V1's visual language. Three
// capabilities that existed only in the old V1 implementation were ported
// back in as part of this promotion, since a migration must preserve every
// existing feature and behavior:
//  - Inline pending-reply review (approve/reject/edit without leaving the
//    dashboard) — see PendingReviewCard below, wired to the same
//    use-pending.ts mutations /pending and Inbox already use.
//  - Retryable error states for the pending-replies and escalations
//    fetches (previously: a failed fetch rendered identically to "nothing
//    to review," which is a silently wrong answer, not just a missing
//    nicety).
//  - The "Learned today" list of actual Knowledge Base entries (not just
//    a count badge) with links to review each one.
// AskHiraBar and the Quick Actions footer remain cut, as already decided
// and reasoned through in the V3 sprints: both duplicated navigation
// available one keystroke (⌘K) or one sidebar click away.
export default function DashboardPage() {
  const { user } = useAuthContext();
  const router = useRouter();

  const {
    data: pending,
    isFetching: isFetchingPending,
    isError: isPendingError,
    refetch: refetchPending,
  } = usePending();
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
  const {
    data: upcomingAppointmentsResult,
    isFetching: isFetchingAppointments,
    isError: isAppointmentsError,
    refetch: refetchAppointments,
  } = useAppointments({ from: now });
  const {
    data: openEscalationsResult,
    isFetching: isFetchingEscalations,
    isError: isEscalationsError,
    refetch: refetchEscalations,
  } = useEscalations({ status: "open", limit: PREVIEW_ROWS });
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

  const highlights = useMemo<BriefHighlight[]>(() => {
    const items: BriefHighlight[] = [];
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

  // A failed pending/escalations fetch means we genuinely don't know
  // whether something needs attention — never collapse that into the
  // reassuring "nothing urgent" read.
  const attentionHasError = isPendingError || isEscalationsError;
  const attentionEmpty =
    !attentionHasError && pendingCount === 0 && escalationCount === 0 && healthAlerts.length === 0;
  const summary = "Here's what's happening with your business.";

  const hubState = healthAlerts.some((a) => a === "whatsapp_disconnected" || a === "ai_failures")
    ? "error"
    : healthAlerts.length > 0
      ? "waiting"
      : "success";

  // Escalations + business-health alerts — the merged inbox list.
  // Pending replies get their own full inline-review treatment below
  // instead of a one-line summary, so they're deliberately not folded
  // into this list.
  const attentionItems = useMemo<AttentionItem[]>(() => {
    const items: AttentionItem[] = [];
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
  }, [openEscalations, healthAlerts, analyticsDashboard, router]);

  // Only render the merged inbox's own positive "nothing needs you" empty
  // state when there's truly nothing anywhere — otherwise, with pending
  // replies sitting in their own card above it, it would contradict itself.
  const showAttentionQueue = attentionItems.length > 0 || pendingCount === 0;

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
      <DashboardHero
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

      {/* Needs Attention (pending replies inline-reviewable, then an inbox
          of escalations + alerts) + AI Workspace (control panel) —
          asymmetric 7/5, attention leading. */}
      <div className="mb-14 grid gap-6 lg:grid-cols-12">
        <div className="space-y-4 lg:col-span-7">
          {isPendingError ? (
            <div className="rounded-2xl bg-card shadow-e2">
              <EmptyState
                icon={AlertTriangle}
                title="Couldn't load pending approvals"
                description="Something went wrong — please try again."
                action={
                  <Button size="sm" onClick={() => refetchPending()}>
                    Retry
                  </Button>
                }
                className="border-0 py-12"
              />
            </div>
          ) : (
            pendingCount > 0 && (
              <div className="rounded-2xl bg-card p-6 shadow-e2 sm:p-7">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="type-title">Pending replies</h2>
                  <span className="text-xs text-muted-foreground">{pendingCount} waiting</span>
                </div>
                <div className="space-y-4">
                  {(pending ?? []).map((p: PendingReply) => (
                    <PendingReviewCard key={p.id} reply={p} />
                  ))}
                </div>
              </div>
            )
          )}

          {isEscalationsError && (
            <div className="rounded-2xl bg-card shadow-e2">
              <EmptyState
                icon={AlertTriangle}
                title="Couldn't load escalations"
                description="Something went wrong — please try again."
                action={
                  <Button size="sm" onClick={() => refetchEscalations()}>
                    Retry
                  </Button>
                }
                className="border-0 py-8"
              />
            </div>
          )}

          {showAttentionQueue && <AttentionQueue items={attentionItems} variant="inbox" />}
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

      {/* Learned today — a small addendum, not its own major section;
          hidden entirely when nothing was added today. */}
      {learnedToday.length > 0 && (
        <Card variant="minimal" className="mb-14">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="text-base">Learned today</CardTitle>
            <MemoryBadge>
              {learnedToday.length} new {pluralize(learnedToday.length, "entry", "entries")}
            </MemoryBadge>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {learnedToday.map((entry) => (
                <li key={entry.id}>
                  <Link
                    href="/knowledge-base"
                    className="block truncate rounded-md px-2 py-1.5 text-sm transition-colors duration-150 hover:bg-accent focus-visible:focus-ring"
                  >
                    {entry.title}
                  </Link>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

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
            <SchedulePanel
              appointments={upcomingAppointments}
              isError={isAppointmentsError}
              onRetry={() => refetchAppointments()}
            />
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
          <RecentLeadsCard leads={recentLeads} className="lg:col-span-7" />
          <div className="lg:col-span-5">
            <RecentCustomersPanel customers={customers} variant="feed" />
          </div>
        </div>
      </div>

      {/* Insights — the page's closing, editorial read of the same period's
          data. It renders nothing itself once there's no conversation data
          yet, so the kicker is gated on the same condition rather than
          heading an empty section. */}
      {analyticsDashboard && analyticsDashboard.overview.total_conversations > 0 && (
        <div>
          <SectionKicker>Insights</SectionKicker>
          <AiInsightsCard data={analyticsDashboard} />
        </div>
      )}
    </>
  );
}

// Inline review, wired directly to the same use-pending.ts hooks (and
// PENDING_KEY cache) this page's own pending-count reads from —
// approve/reject/edit optimistically remove the card and decrement the
// count in the same tick, no waiting on a network round-trip. Customer name
// renders above the card since ReviewReplyCard has no slot for it (correct
// for Inbox, where the conversation itself already establishes who — this
// list spans multiple customers at once).
function PendingReviewCard({ reply }: { reply: PendingReply }) {
  const { toast } = useToast();
  const approve = useApprove();
  const reject = useReject();
  const updateDraft = useUpdateDraft();

  const pending = approve.isPending || reject.isPending || updateDraft.isPending;
  const onError = (action: string) => () =>
    toast({ title: `Couldn't ${action} the reply`, description: "Please try again.", variant: "destructive" });

  const review = reply.review;

  return (
    <div className="space-y-2">
      <div className="flex min-w-0 items-center justify-between gap-2">
        <span className="min-w-0 truncate text-sm font-medium">{customerLabel(reply.customer)}</span>
        <span className="shrink-0 text-xs text-muted-foreground">
          {formatRelativeTime(reply.created_at)}
        </span>
      </div>
      <ReviewReplyCard
        body={reply.body}
        status={approve.isPending ? "sending" : "waiting"}
        confidence={review?.confidence?.level ?? undefined}
        groundedCount={review?.grounding?.retrieved_count ?? undefined}
        groundingSources={review?.grounding?.sources ?? undefined}
        generationStatus={review?.generation_status}
        pending={pending}
        onApprove={() => approve.mutate(reply.id, { onError: onError("approve") })}
        onReject={() => reject.mutate(reply.id, { onError: onError("reject") })}
        onEdit={(nextBody) =>
          updateDraft.mutate({ id: reply.id, body: nextBody }, { onError: onError("save") })
        }
      />
    </div>
  );
}
