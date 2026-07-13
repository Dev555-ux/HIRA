"use client";

import {
  AlertTriangle,
  CalendarClock,
  CheckCheck,
  Inbox as InboxIcon,
  MessageSquare,
  RefreshCw,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";
import { EmptyState } from "@/components/empty-state";
import { OnboardingChecklist } from "@/components/onboarding-checklist";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAppointments } from "@/hooks/use-appointments";
import { useConversations } from "@/hooks/use-conversations";
import { useCustomers } from "@/hooks/use-customers";
import { useOnboardingStatus } from "@/hooks/use-onboarding";
import { usePending } from "@/hooks/use-pending";
import { APPOINTMENT_STATUS_BADGE, formatAppointmentRange } from "@/lib/appointments";
import { CONVERSATION_STATUS_BADGE } from "@/lib/conversations";
import { describeWhatsAppConnection, formatRelativeTime } from "@/lib/utils";

// How many rows each preview widget shows before "View all" takes over —
// kept small and consistent across widgets so the page reads as an at-a-
// glance overview, not a second copy of each full list page.
const PREVIEW_ROWS = 5;

export default function DashboardPage() {
  const {
    data: pending,
    isLoading: isLoadingPending,
    isFetching: isFetchingPending,
    isError: isPendingError,
    refetch: refetchPending,
  } = usePending();
  const { data: onboarding } = useOnboardingStatus();
  // limit: 1 — only meta.total is needed here, not the rows themselves.
  const {
    data: conversationTotals,
    isLoading: isLoadingConversationTotals,
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
    isLoading: isLoadingCustomers,
    isError: isCustomersError,
  } = useCustomers({ limit: 1 });
  // Computed once per mount (matches the Appointments page's own convention)
  // rather than on every render, so the query key — and therefore the
  // request — doesn't change on each re-render.
  const now = useMemo(() => new Date().toISOString(), []);
  const {
    data: upcomingAppointmentsResult,
    isLoading: isLoadingAppointments,
    isFetching: isFetchingAppointments,
    isError: isAppointmentsError,
    refetch: refetchAppointments,
  } = useAppointments({ from: now });

  const whatsapp = describeWhatsAppConnection(onboarding?.business?.whatsapp_connection_status);
  const upcomingAppointments = upcomingAppointmentsResult ?? [];
  const recentConversations = recentConversationsPage?.data ?? [];
  const isRefreshing = isFetchingPending || isFetchingConversations || isFetchingAppointments;

  function refreshAll() {
    refetchPending();
    refetchConversations();
    refetchAppointments();
  }

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Overview of your AI employee."
        action={
          <Button variant="outline" size="sm" onClick={refreshAll}>
            <RefreshCw className={isRefreshing ? "animate-spin" : ""} />
            Refresh
          </Button>
        }
      />

      {onboarding?.business && onboarding.business.onboarding_status !== "live" && (
        <OnboardingChecklist business={onboarding.business} />
      )}

      {/* KPIs — the four numbers an owner checks first. */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Pending approvals"
          value={isPendingError ? "—" : (pending?.length ?? 0)}
          icon={CheckCheck}
          loading={isLoadingPending}
          hint={isPendingError ? "Couldn't load" : "Replies awaiting review"}
        />
        <StatCard
          label="Conversations"
          value={isConversationTotalsError ? "—" : (conversationTotals?.meta.total ?? 0)}
          icon={MessageSquare}
          loading={isLoadingConversationTotals}
          hint={isConversationTotalsError ? "Couldn't load" : "Total conversations"}
        />
        <StatCard
          label="Customers"
          value={isCustomersError ? "—" : (customers?.meta.total ?? 0)}
          icon={Users}
          loading={isLoadingCustomers}
          hint={isCustomersError ? "Couldn't load" : "People who have messaged you"}
        />
        <StatCard
          label="Upcoming appointments"
          value={isAppointmentsError ? "—" : upcomingAppointments.length}
          icon={CalendarClock}
          loading={isLoadingAppointments}
          hint={isAppointmentsError ? "Couldn't load" : "Booked and scheduled"}
        />
      </div>

      {/* Primary row: what needs action now, and what's coming up next. */}
      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
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
                className="border-0 py-10"
              />
            ) : (pending?.length ?? 0) === 0 ? (
              <EmptyState
                icon={CheckCheck}
                title="Nothing pending"
                description="AI replies awaiting approval will appear here."
                className="border-0 py-10"
              />
            ) : (
              <ul className="divide-y">
                {pending!.slice(0, PREVIEW_ROWS).map((p) => {
                  const name = p.customer?.display_name || p.customer?.wa_phone || "Unknown customer";
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
          <Card>
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
                  className="border-0 py-8"
                />
              ) : upcomingAppointments.length === 0 ? (
                <EmptyState
                  icon={CalendarClock}
                  title="No upcoming appointments"
                  description="Bookings the AI (or you) make will show up here."
                  action={
                    <Button asChild size="sm" variant="outline">
                      <Link href="/appointments">New appointment</Link>
                    </Button>
                  }
                  className="border-0 py-8"
                />
              ) : (
                <ul className="space-y-3">
                  {upcomingAppointments.slice(0, 4).map((appt) => {
                    const badge = APPOINTMENT_STATUS_BADGE[appt.status];
                    const name =
                      appt.customer?.display_name || appt.customer?.wa_phone || "Unknown customer";
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

          <Card>
            <CardHeader>
              <CardTitle className="text-base">System status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <StatusRow label="AI provider (Groq)" ok />
              <StatusRow label="Embeddings (local bge-small)" ok />
              <StatusRow
                label="WhatsApp integration"
                ok={onboarding?.business?.whatsapp_connection_status === "connected"}
                note={whatsapp.label}
                variant={whatsapp.variant}
              />
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Secondary row: recent activity across the whole inbox. */}
      <Card className="mt-4">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="text-base">Recent conversations</CardTitle>
          <Button asChild size="sm" variant="ghost">
            <Link href="/inbox">View all</Link>
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          {isRecentConversationsError ? (
            <EmptyState
              icon={AlertTriangle}
              title="Couldn't load conversations"
              description="Something went wrong — please try again."
              action={
                <Button size="sm" onClick={() => refetchConversations()}>
                  Retry
                </Button>
              }
              className="border-0 py-10"
            />
          ) : recentConversations.length === 0 ? (
            <EmptyState
              icon={InboxIcon}
              title="No conversations yet"
              description="Conversations started by customers on WhatsApp will show up here. While you wait, try the Playground to see how the Receptionist responds."
              action={
                <Button asChild size="sm" variant="outline">
                  <Link href="/playground">Try the Playground</Link>
                </Button>
              }
              className="border-0 py-10"
            />
          ) : (
            <ul className="divide-y">
              {recentConversations.map((conv) => {
                const badge = CONVERSATION_STATUS_BADGE[conv.status];
                const name = conv.customer.display_name || conv.customer.wa_phone;
                return (
                  <li
                    key={conv.id}
                    className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-6 py-3"
                  >
                    <div className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{name}</span>
                      <p className="truncate text-xs text-muted-foreground">
                        {conv.preview ?? "No messages yet"}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {conv.has_pending_approval && <Badge variant="warning">Pending</Badge>}
                      <Badge variant={badge.variant}>{badge.label}</Badge>
                      {conv.last_message_at && (
                        <span className="w-16 text-right text-xs text-muted-foreground">
                          {formatRelativeTime(conv.last_message_at)}
                        </span>
                      )}
                    </div>
                  </li>
                );
              })}
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
