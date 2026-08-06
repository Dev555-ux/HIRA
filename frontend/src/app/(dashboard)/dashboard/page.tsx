"use client";

import {
  AlertTriangle,
  CalendarClock,
  CheckCheck,
  MessageSquare,
  Sparkles,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";
import { DashboardHero } from "@/components/dashboard-hero";
import { EmptyState } from "@/components/empty-state";
import { OnboardingChecklist } from "@/components/onboarding-checklist";
import { ReviewReplyCard } from "@/components/review-reply-card";
import { StatCard } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusPill } from "@/components/ui/status-pill";
import { useToast } from "@/components/ui/toast";
import { useAppointments } from "@/hooks/use-appointments";
import { useAuthContext } from "@/lib/auth-context";
import { useConversations } from "@/hooks/use-conversations";
import { useCustomers } from "@/hooks/use-customers";
import { useOnboardingStatus } from "@/hooks/use-onboarding";
import { useApprove, usePending, useReject, useUpdateDraft } from "@/hooks/use-pending";
import type { Appointment, PendingReply } from "@/lib/types";
import { APPOINTMENT_STATUS, APPOINTMENT_STATUS_BADGE, formatAppointmentRange } from "@/lib/appointments";
import { VARIANT_TO_STATE } from "@/lib/status";
import { describeWhatsAppConnection, formatRelativeTime } from "@/lib/utils";

// How many rows each preview widget shows before "View all" takes over —
// kept small and consistent across widgets so the page reads as an at-a-
// glance overview, not a second copy of each full list page.
const PREVIEW_ROWS = 5;
const ACTIVITY_ROWS = 6;

function customerLabel(customer: { display_name: string | null; wa_phone: string } | null): string {
  return customer?.display_name || customer?.wa_phone || "Unknown customer";
}

function pluralize(count: number, singular: string, plural: string): string {
  return count === 1 ? singular : plural;
}

interface ActivityEntry {
  id: string;
  icon: typeof CheckCheck;
  title: string;
  detail: string;
  timestamp: string;
}

export default function DashboardPage() {
  const { user } = useAuthContext();
  const {
    data: pending,
    isPending: isLoadingPending,
    isFetching: isFetchingPending,
    isError: isPendingError,
    refetch: refetchPending,
  } = usePending();
  const { data: onboarding, isFetching: isFetchingOnboarding, refetch: refetchOnboarding } =
    useOnboardingStatus();
  // limit: 1 — only meta.total is needed here, not the rows themselves.
  const {
    data: conversationTotals,
    isPending: isLoadingConversationTotals,
    isError: isConversationTotalsError,
    isFetching: isFetchingConversationTotals,
    refetch: refetchConversationTotals,
  } = useConversations({ limit: 1 });
  const {
    data: recentConversationsPage,
    isFetching: isFetchingConversations,
    isError: isRecentConversationsError,
    refetch: refetchConversations,
  } = useConversations({ limit: PREVIEW_ROWS });
  const {
    data: customers,
    isPending: isLoadingCustomers,
    isError: isCustomersError,
    isFetching: isFetchingCustomers,
    refetch: refetchCustomers,
  } = useCustomers({ limit: 1 });
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

  const whatsapp = describeWhatsAppConnection(onboarding?.business?.whatsapp_connection_status);
  const upcomingAppointments = useMemo(
    () => upcomingAppointmentsResult ?? [],
    [upcomingAppointmentsResult],
  );
  const recentConversations = useMemo(
    () => recentConversationsPage?.data ?? [],
    [recentConversationsPage],
  );
  const isRefreshing =
    isFetchingPending ||
    isFetchingOnboarding ||
    isFetchingConversationTotals ||
    isFetchingConversations ||
    isFetchingCustomers ||
    isFetchingAppointments;

  function refreshAll() {
    refetchPending();
    refetchOnboarding();
    refetchConversationTotals();
    refetchConversations();
    refetchCustomers();
    refetchAppointments();
  }

  // A compact, chronological merge of activity already fetched for the KPIs
  // and preview widgets above — no new endpoint, no invented events. Each
  // source contributes a short, distinctly-framed line so it reads as a log
  // of what happened rather than repeating "Needs your attention"'s full
  // draft text or "Upcoming appointments"'s own listing verbatim.
  const activity = useMemo<ActivityEntry[]>(() => {
    const entries: ActivityEntry[] = [];
    const pendingConversationIds = new Set((pending ?? []).map((p) => p.conversation_id));
    for (const p of pending ?? []) {
      entries.push({
        id: `pending-${p.id}`,
        icon: CheckCheck,
        title: customerLabel(p.customer),
        detail: "Reply drafted, awaiting your approval",
        timestamp: p.created_at,
      });
    }
    for (const c of recentConversations) {
      // A conversation whose latest message *is* a still-pending draft
      // already has its own, more specific entry above (and its own badge
      // in "Needs your attention") — showing it again here with the same
      // draft text as a generic "conversation preview" read as the same
      // event happening twice.
      if (pendingConversationIds.has(c.id)) continue;
      entries.push({
        id: `conversation-${c.id}`,
        icon: MessageSquare,
        title: customerLabel(c.customer),
        detail: c.preview ?? "Started a conversation",
        timestamp: c.last_message_at ?? c.created_at,
      });
    }
    for (const a of upcomingAppointments) {
      entries.push({
        id: `appointment-${a.id}`,
        icon: CalendarClock,
        title: customerLabel(a.customer),
        detail: `Appointment booked for ${formatAppointmentRange(a.starts_at, a.ends_at)}`,
        timestamp: a.created_at,
      });
    }
    return entries
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
      .slice(0, ACTIVITY_ROWS);
  }, [pending, recentConversations, upcomingAppointments]);

  const pendingCount = pending?.length ?? 0;
  const appointmentCount = upcomingAppointments.length;
  const summaryReady =
    !isLoadingPending && !isPendingError && !isLoadingAppointments && !isAppointmentsError;
  const summary = summaryReady
    ? `You have ${pendingCount === 0 ? "no" : pendingCount} ${pluralize(pendingCount, "reply", "replies")} waiting for review and ${appointmentCount === 0 ? "no" : appointmentCount} ${pluralize(appointmentCount, "appointment", "appointments")} booked.`
    : "Here's what's happening with your business.";

  return (
    <>
      <DashboardHero
        name={user?.name ?? "there"}
        summary={summary}
        isRefreshing={isRefreshing}
        onRefresh={refreshAll}
        pendingCount={pendingCount}
      />

      {onboarding?.business && onboarding.business.onboarding_status !== "live" && (
        <OnboardingChecklist business={onboarding.business} />
      )}

      {/* KPIs — the four numbers an owner checks first. */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Pending approvals"
          value={isPendingError ? "—" : pendingCount}
          icon={CheckCheck}
          loading={isLoadingPending}
          hint={
            isPendingError ? "Couldn't load" : pendingCount === 0 ? "Everything reviewed" : "Awaiting your review"
          }
        />
        <StatCard
          label="Conversations"
          value={isConversationTotalsError ? "—" : (conversationTotals?.meta.total ?? 0)}
          icon={MessageSquare}
          loading={isLoadingConversationTotals}
          hint={
            isConversationTotalsError
              ? "Couldn't load"
              : (conversationTotals?.meta.total ?? 0) === 0
                ? "No conversations yet"
                : "Across all customers"
          }
        />
        <StatCard
          label="Customers"
          value={isCustomersError ? "—" : (customers?.meta.total ?? 0)}
          icon={Users}
          loading={isLoadingCustomers}
          hint={
            isCustomersError
              ? "Couldn't load"
              : (customers?.meta.total ?? 0) === 0
                ? "No one yet"
                : "People who've messaged you"
          }
        />
        <StatCard
          label="Upcoming appointments"
          value={isAppointmentsError ? "—" : appointmentCount}
          icon={CalendarClock}
          loading={isLoadingAppointments}
          hint={isAppointmentsError ? "Couldn't load" : appointmentCount === 0 ? "Nothing scheduled" : "Booked and scheduled"}
        />
      </div>

      {/* Primary row: what needs action now, and what's coming up next. */}
      <div className="mt-8 grid gap-4 lg:grid-cols-3">
        <Card interactive className="lg:col-span-2">
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
            ) : pendingCount === 0 ? (
              <EmptyState
                icon={CheckCheck}
                title="Nothing pending"
                description="HIRA is keeping up — a new reply will show up here the moment a customer writes in and needs your review."
                className="border-0 py-12"
              />
            ) : (
              <div className="space-y-4">
                {pending!.slice(0, PREVIEW_ROWS).map((p: PendingReply) => (
                  <DashboardReviewCard key={p.id} reply={p} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <div className="flex flex-col gap-4">
          <Card interactive>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle className="text-base">Upcoming appointments</CardTitle>
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

          <Card interactive className="bg-muted/30">
            <CardHeader>
              <CardTitle className="text-base">WhatsApp status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <StatusRow
                label="WhatsApp"
                ok={onboarding?.business?.whatsapp_connection_status === "connected"}
                note={whatsapp.label}
                variant={whatsapp.variant}
              />
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Secondary row: a compact, chronological log across conversations,
          approvals, and bookings — a retrospective "what happened" view,
          distinct from "Needs your attention"'s prescriptive "what to do
          now." */}
      <Card interactive className="mt-8">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="text-base">Recent activity</CardTitle>
          <Button asChild size="sm" variant="ghost">
            <Link href="/inbox">View all</Link>
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          {isRecentConversationsError ? (
            <EmptyState
              icon={AlertTriangle}
              title="Couldn't load activity"
              description="Something went wrong — please try again."
              action={
                <Button size="sm" onClick={() => refetchConversations()}>
                  Retry
                </Button>
              }
              className="border-0 py-12"
            />
          ) : activity.length === 0 ? (
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
              {activity.map((entry) => (
                <li key={entry.id} className="group flex items-center gap-3 px-6 py-3">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 transition-colors duration-200 group-hover:bg-primary/15">
                    <entry.icon className="size-4 text-primary" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{entry.title}</p>
                    <p className="truncate text-xs text-muted-foreground">{entry.detail}</p>
                  </div>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {formatRelativeTime(entry.timestamp)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </>
  );
}

function StatusRow({
  label,
  ok,
  note,
  variant,
}: {
  label: string;
  ok: boolean;
  note?: string;
  variant?: "success" | "warning" | "secondary";
}) {
  const resolvedVariant = variant ?? (ok ? "success" : "secondary");
  return (
    <div className="flex items-center justify-between">
      <span>{label}</span>
      <StatusPill state={VARIANT_TO_STATE[resolvedVariant]}>
        {note ?? (ok ? "Operational" : "Off")}
      </StatusPill>
    </div>
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
