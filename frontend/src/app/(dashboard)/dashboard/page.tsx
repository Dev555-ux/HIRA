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
import { StatCard } from "@/components/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAppointments } from "@/hooks/use-appointments";
import { useAuthContext } from "@/lib/auth-context";
import { useConversations } from "@/hooks/use-conversations";
import { useCustomers } from "@/hooks/use-customers";
import { useOnboardingStatus } from "@/hooks/use-onboarding";
import { usePending } from "@/hooks/use-pending";
import type { Appointment, PendingReply } from "@/lib/types";
import { APPOINTMENT_STATUS_BADGE, formatAppointmentRange } from "@/lib/appointments";
import { describeWhatsAppConnection, formatRelativeTime } from "@/lib/utils";

// How many rows each preview widget shows before "View all" takes over —
// kept small and consistent across widgets so the page reads as an at-a-
// glance overview, not a second copy of each full list page.
const PREVIEW_ROWS = 5;
const ACTIVITY_ROWS = 6;

// Shared, restrained hover treatment for this page's content cards (Sprint
// 46) — a ~2px lift and a slightly deeper shadow, nothing else. Kept as one
// constant so all four cards below move identically rather than each
// hand-rolling a slightly different value.
const CARD_HOVER = "transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-md";

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
  const { data: onboarding } = useOnboardingStatus();
  // limit: 1 — only meta.total is needed here, not the rows themselves.
  const {
    data: conversationTotals,
    isPending: isLoadingConversationTotals,
    isError: isConversationTotalsError,
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
  const isRefreshing = isFetchingPending || isFetchingConversations || isFetchingAppointments;

  function refreshAll() {
    refetchPending();
    refetchConversations();
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
        <Card className={`lg:col-span-2 ${CARD_HOVER}`}>
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
              <ul className="divide-y">
                {pending!.slice(0, PREVIEW_ROWS).map((p: PendingReply) => {
                  const name = customerLabel(p.customer);
                  return (
                    <li key={p.id} className="flex items-start justify-between gap-3 py-3 first:pt-0 last:pb-0">
                      <div className="min-w-0 flex-1">
                        <div className="flex min-w-0 items-center gap-2">
                          <span className="min-w-0 truncate text-sm font-medium">{name}</span>
                          <span className="shrink-0 text-xs text-muted-foreground">
                            {formatRelativeTime(p.created_at)}
                          </span>
                        </div>
                        <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">{p.body}</p>
                      </div>
                      <Badge variant="warning" className="shrink-0">
                        Pending
                      </Badge>
                    </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>

        <div className="flex flex-col gap-4">
          <Card className={CARD_HOVER}>
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
                        <Badge variant={badge.variant} className="shrink-0">
                          {badge.label}
                        </Badge>
                      </li>
                    );
                  })}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card className={`bg-muted/30 ${CARD_HOVER}`}>
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
      <Card className={`mt-8 ${CARD_HOVER}`}>
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
  return (
    <div className="flex items-center justify-between">
      <span>{label}</span>
      <Badge variant={variant ?? (ok ? "success" : "secondary")}>
        {note ?? (ok ? "Operational" : "Off")}
      </Badge>
    </div>
  );
}
