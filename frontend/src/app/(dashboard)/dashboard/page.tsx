"use client";

import {
  AlertTriangle,
  CalendarClock,
  CheckCheck,
  MessageSquare,
  Sparkles,
  UserPlus,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";
import { AskHiraBar } from "@/components/ask-hira-bar";
import { DashboardHero, type BriefHighlight } from "@/components/dashboard-hero";
import { EmptyState } from "@/components/empty-state";
import { OnboardingChecklist } from "@/components/onboarding-checklist";
import { ReviewReplyCard } from "@/components/review-reply-card";
import { BusinessHealthCard } from "@/components/ui/business-health-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MemoryBadge } from "@/components/ui/memory-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusPill } from "@/components/ui/status-pill";
import { TaskCard } from "@/components/ui/task-card";
import { useToast } from "@/components/ui/toast";
import { useAiActivity } from "@/hooks/use-activity";
import { useAnalyticsDashboard } from "@/hooks/use-analytics";
import { useAppointments } from "@/hooks/use-appointments";
import { useAuthContext } from "@/lib/auth-context";
import { useEscalations } from "@/hooks/use-escalations";
import { useKbEntries } from "@/hooks/use-knowledge-base";
import { useLeads } from "@/hooks/use-leads";
import { useOnboardingStatus } from "@/hooks/use-onboarding";
import { useApprove, usePending, useReject, useUpdateDraft } from "@/hooks/use-pending";
import type { AiActivityOutcome, Appointment, Escalation, PendingReply } from "@/lib/types";
import { APPOINTMENT_STATUS, APPOINTMENT_STATUS_BADGE, formatAppointmentRange } from "@/lib/appointments";
import { cn, formatRelativeTime } from "@/lib/utils";

// How many rows each preview widget shows before "View all" takes over —
// kept small and consistent across widgets so the page reads as an at-a-
// glance overview, not a second copy of each full list page.
const PREVIEW_ROWS = 5;
const ACTIVITY_ROWS = 6;

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
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

// Sprint 84 (Dashboard Foundation): outcome -> icon for the AI Activity feed.
// No new icon imports needed — every outcome maps to one of the icons this
// page already uses elsewhere (Morning Brief highlights, Needs your
// attention), so the feed and the rest of Home stay visually consistent.
function activityIcon(outcome: AiActivityOutcome): typeof CheckCheck {
  if (outcome === "escalated" || outcome === "failed") return AlertTriangle;
  if (outcome === "pending_approval" || outcome === "sending" || outcome === "rejected") {
    return MessageSquare;
  }
  return CheckCheck;
}

export default function DashboardPage() {
  const { user } = useAuthContext();
  const router = useRouter();
  const {
    data: pending,
    isPending: isLoadingPending,
    isFetching: isFetchingPending,
    isError: isPendingError,
    refetch: refetchPending,
  } = usePending();
  const { data: onboarding, isFetching: isFetchingOnboarding, refetch: refetchOnboarding } =
    useOnboardingStatus();
  // AI activity (Sprint 84, Dashboard Foundation) — a real read over
  // execution_traces (GET /api/v1/activity), replacing the old client-side
  // merge of conversations/pending/appointments. See
  // app/services/execution_traces.py::list_activity_for_dashboard.
  const {
    data: aiActivityResult,
    isPending: isLoadingActivity,
    isFetching: isFetchingActivity,
    isError: isActivityError,
    refetch: refetchActivity,
  } = useAiActivity(ACTIVITY_ROWS);
  // Morning Brief's "N new leads" line — same small-page-then-client-filter
  // pattern as "Learned today" below (no new endpoint, no date-range param
  // on this list endpoint to ask the backend for "today" directly).
  const {
    data: recentLeadsPage,
    isFetching: isFetchingLeads,
    refetch: refetchLeads,
  } = useLeads({ limit: PREVIEW_ROWS });
  // Computed once per mount (matches the Appointments page's own convention)
  // rather than on every render, so the query key — and therefore the
  // request — doesn't change on each re-render.
  const now = useMemo(() => new Date().toISOString(), []);
  const {
    data: upcomingAppointmentsResult,
    isPending: isLoadingAppointments,
    isFetching: isFetchingAppointments,
    isError: isAppointmentsError,
    refetch: refetchAppointments,
  } = useAppointments({ from: now });
  const {
    data: openEscalationsResult,
    isPending: isLoadingEscalations,
    isFetching: isFetchingEscalations,
    isError: isEscalationsError,
    refetch: refetchEscalations,
  } = useEscalations({ status: "open", limit: PREVIEW_ROWS });
  // Business Health (§4) reuses the Phase 1 BusinessHealthCard, which reuses
  // the Analytics dashboard's own business_health field — the only place
  // this data already exists. Range fixed at 30d; Home isn't a range-picker.
  const {
    data: analyticsDashboard,
    isFetching: isFetchingAnalytics,
    refetch: refetchAnalytics,
  } = useAnalyticsDashboard("30d");
  // Learned Today (§8) reuses the Knowledge Base's own entry list, filtered
  // client-side to today — no new endpoint, no invented "learning event."
  const {
    data: kbEntries,
    isFetching: isFetchingKb,
    refetch: refetchKb,
  } = useKbEntries();

  const upcomingAppointments = useMemo(
    () => upcomingAppointmentsResult ?? [],
    [upcomingAppointmentsResult],
  );
  const aiActivity = useMemo(() => aiActivityResult ?? [], [aiActivityResult]);
  const openEscalations = useMemo(() => openEscalationsResult?.data ?? [], [openEscalationsResult]);
  const learnedToday = useMemo(
    () => (kbEntries ?? []).filter((entry) => isToday(entry.created_at)),
    [kbEntries],
  );
  // Morning Brief highlights (§1) — every count here is real and today-
  // scoped, computed from data already fetched for the sections below (plus
  // one small new leads page). A zero-count line is omitted rather than
  // shown, per "if something can't be honestly stated, simplify instead."
  const repliesToday = analyticsDashboard?.overview.ai_responses_today ?? 0;
  const appointmentsBookedToday = useMemo(
    () => upcomingAppointments.filter((a) => isToday(a.created_at)).length,
    [upcomingAppointments],
  );
  const leadsToday = useMemo(
    () => (recentLeadsPage?.data ?? []).filter((l) => isToday(l.created_at)).length,
    [recentLeadsPage],
  );
  const escalationsToday = useMemo(
    () => openEscalations.filter((e) => isToday(e.created_at)).length,
    [openEscalations],
  );
  const highlights = useMemo<BriefHighlight[]>(() => {
    const items: BriefHighlight[] = [];
    if (repliesToday > 0) {
      items.push({
        icon: CheckCheck,
        label: `Answered ${repliesToday} customer ${pluralize(repliesToday, "message", "messages")}`,
      });
    }
    if (appointmentsBookedToday > 0) {
      items.push({
        icon: CalendarClock,
        label: `Booked ${appointmentsBookedToday} ${pluralize(appointmentsBookedToday, "appointment", "appointments")}`,
      });
    }
    if (leadsToday > 0) {
      items.push({ icon: UserPlus, label: `${leadsToday} new ${pluralize(leadsToday, "lead", "leads")}` });
    }
    if (escalationsToday > 0) {
      items.push({
        icon: AlertTriangle,
        label: `Escalated ${escalationsToday} ${pluralize(escalationsToday, "conversation", "conversations")} for your review`,
      });
    }
    return items;
  }, [repliesToday, appointmentsBookedToday, leadsToday, escalationsToday]);
  const isRefreshing =
    isFetchingPending ||
    isFetchingOnboarding ||
    isFetchingActivity ||
    isFetchingLeads ||
    isFetchingAppointments ||
    isFetchingEscalations ||
    isFetchingAnalytics ||
    isFetchingKb;

  function refreshAll() {
    refetchPending();
    refetchOnboarding();
    refetchActivity();
    refetchLeads();
    refetchAppointments();
    refetchEscalations();
    refetchAnalytics();
    refetchKb();
  }

  const pendingCount = pending?.length ?? 0;
  const escalationCount = openEscalations.length;
  const appointmentCount = upcomingAppointments.length;
  const summaryReady =
    !isLoadingPending &&
    !isPendingError &&
    !isLoadingAppointments &&
    !isAppointmentsError &&
    !isLoadingEscalations &&
    !isEscalationsError;
  const baseSummary = summaryReady
    ? `You have ${pendingCount === 0 ? "no" : pendingCount} ${pluralize(pendingCount, "reply", "replies")} waiting for review and ${appointmentCount === 0 ? "no" : appointmentCount} ${pluralize(appointmentCount, "appointment", "appointments")} booked.`
    : "Here's what's happening with your business.";
  // Escalations are mentioned only when there are any — an "and 0 escalated"
  // clause on every good day would bury the one day it actually matters.
  const summary =
    summaryReady && escalationCount > 0
      ? `${baseSummary} ${escalationCount} ${pluralize(escalationCount, "conversation", "conversations")} escalated to you.`
      : baseSummary;

  // "Needs your attention" (§3): pending replies + open escalations, merged.
  // Sprint 84: this now always renders (see the Card below) — attentionEmpty
  // only decides which body it shows (the queue, or a calm "nothing needs
  // you" state), not whether the card exists at all.
  const attentionHasError = isPendingError || isEscalationsError;
  const attentionEmpty = !attentionHasError && pendingCount === 0 && escalationCount === 0;

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
      />

      <div className="mb-8">
        <AskHiraBar />
      </div>

      {onboarding?.business && onboarding.business.onboarding_status !== "live" && (
        <OnboardingChecklist business={onboarding.business} />
      )}

      {/* Sprint 84 (Dashboard Foundation): Needs Your Attention is the
          primary workspace, not a card that disappears when there's nothing
          to review — it always renders, with a calm, positive empty state
          when there's genuinely nothing pending. The warning-colored spine
          only appears when something actually needs a decision. */}
      <Card interactive className={cn("mb-8", !attentionEmpty && "border-l-2 border-l-warning")}>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="text-base">Needs your attention</CardTitle>
          <Button asChild size="sm" variant="ghost">
            <Link href="/pending">View all</Link>
          </Button>
        </CardHeader>
        <CardContent>
          {isPendingError ? (
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
          ) : attentionEmpty ? (
            <EmptyState
              icon={CheckCheck}
              title="Nothing needs you right now"
              description="Approvals and escalated conversations will show up here the moment something needs a decision."
              className="border-0 py-12"
            />
          ) : (
            <div className="space-y-4">
              {(pending ?? []).slice(0, PREVIEW_ROWS).map((p: PendingReply) => (
                <DashboardReviewCard key={p.id} reply={p} />
              ))}
              {isEscalationsError ? (
                <EmptyState
                  icon={AlertTriangle}
                  title="Couldn't load escalations"
                  description="Something went wrong — please try again."
                  action={
                    <Button size="sm" onClick={() => refetchEscalations()}>
                      Retry
                    </Button>
                  }
                  className="border-0 py-6"
                />
              ) : (
                openEscalations.slice(0, PREVIEW_ROWS).map((escalation: Escalation) => (
                  <TaskCard
                    key={escalation.id}
                    title={customerLabel(escalation.conversation.customer)}
                    description="Escalated — needs your review"
                    meta={
                      <span className="type-caption text-muted-foreground">
                        {formatRelativeTime(escalation.created_at)}
                      </span>
                    }
                    action={{ label: "Review", onClick: () => router.push("/escalations") }}
                  />
                ))
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {analyticsDashboard?.business_health && (
        <div className="mb-8">
          <BusinessHealthCard health={analyticsDashboard.business_health} explain />
        </div>
      )}

      {/* AI activity (Sprint 84, Dashboard Foundation) — real execution_traces,
          read back as a narrative log ("what HIRA has actually done"),
          replacing the old client-synthesized feed. Distinct from "Needs
          your attention"'s prescriptive "what to do now." */}
      <Card interactive className="mt-8">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="text-base">AI activity</CardTitle>
          <Button asChild size="sm" variant="ghost">
            <Link href="/inbox">View all</Link>
          </Button>
        </CardHeader>
        <CardContent className="p-0">
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
            <div className="space-y-3 px-6 py-4">
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
            <ul className="divide-y" data-testid="activity-feed">
              {aiActivity.map((entry) => {
                const Icon = activityIcon(entry.outcome);
                return (
                  <li key={entry.id} className="group flex items-center gap-3 px-6 py-3">
                    <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 transition-colors duration-200 group-hover:bg-primary/15">
                      <Icon className="size-4 text-primary" />
                    </div>
                    <p className="min-w-0 flex-1 truncate text-sm font-medium">{entry.summary}</p>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {formatRelativeTime(entry.created_at)}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* Today's schedule — reference material for "what's coming up next,"
          not one of the first-viewport questions, so it sits here,
          lightweight (muted surface, not `interactive`), after the sections
          that actually answer those questions. */}
      <Card className="mt-8 bg-muted/30">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="text-base">Today&apos;s schedule</CardTitle>
          <Button asChild size="sm" variant="ghost">
            <Link href="/appointments">View all</Link>
          </Button>
        </CardHeader>
        <CardContent>
          {isAppointmentsError ? (
            <EmptyState
              icon={AlertTriangle}
              title="Couldn't load"
              description="Something went wrong — please try again."
              action={
                <Button size="sm" onClick={() => refetchAppointments()}>
                  Retry
                </Button>
              }
              className="border-0 py-10"
            />
          ) : appointmentCount === 0 ? (
            <EmptyState
              icon={CalendarClock}
              title="No upcoming appointments"
              description="Once a customer confirms a time — or you book one yourself — it'll show up here."
              action={
                <Button asChild size="sm" variant="outline">
                  <Link href="/appointments">New appointment</Link>
                </Button>
              }
              className="border-0 py-10"
            />
          ) : (
            <ul className="space-y-3">
              {upcomingAppointments.slice(0, 4).map((appt: Appointment) => {
                const badge = APPOINTMENT_STATUS_BADGE[appt.status];
                const name = customerLabel(appt.customer);
                return (
                  <li key={appt.id} className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{name}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatAppointmentRange(appt.starts_at, appt.ends_at)}
                      </p>
                    </div>
                    <StatusPill state={APPOINTMENT_STATUS[appt.status]} className="shrink-0">
                      {badge.label}
                    </StatusPill>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* Learned Today (§8) — hidden entirely when nothing was added today,
          same "don't announce nothing" rule as Needs your attention. */}
      {learnedToday.length > 0 && (
        <Card interactive className="mt-8">
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
                    className="block truncate rounded-md px-2 py-1.5 text-sm hover:bg-accent"
                  >
                    {entry.title}
                  </Link>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </>
  );
}

// M10: inline review, wired directly to the same use-pending.ts hooks (and
// PENDING_KEY cache) this page's own "Pending approvals" KPI and this list
// already read from — approve/reject optimistically remove the row and
// decrement the KPI in the same tick, no waiting on a network round-trip or
// the next poll. Deliberately not PendingReviewContainer (Inbox's Message +
// usePendingReplyActions/CONVERSATIONS_KEY combination): reusing it here
// would leave this list and the KPI tile disagreeing until the next 15s
// poll. Customer name renders above the card since ReviewReplyCard has no
// slot for it (correct for Inbox, where the conversation itself already
// establishes who — this list spans multiple customers at once).
function DashboardReviewCard({ reply }: { reply: PendingReply }) {
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
