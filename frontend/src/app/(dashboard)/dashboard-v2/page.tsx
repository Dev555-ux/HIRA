"use client";

import {
  AlertTriangle,
  BookOpen,
  CalendarClock,
  CheckCheck,
  MessageSquareText,
  Sparkles,
  UserPlus,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo } from "react";
import Link from "next/link";
import { ActivityTimeline } from "@/components/dashboard-activity-timeline";
import { AiTeamPanel } from "@/components/dashboard-v2-ai-team";
import { AttentionQueue, type AttentionItem } from "@/components/dashboard-v2-attention-queue";
import { RecentCustomersPanel } from "@/components/dashboard-v2-customers";
import { DashboardV2Hero, type RosterEntry, type V2Highlight } from "@/components/dashboard-v2-hero";
import { SchedulePanel } from "@/components/dashboard-v2-schedule";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useAiActivity } from "@/hooks/use-activity";
import { useAnalyticsDashboard } from "@/hooks/use-analytics";
import { useAppointments } from "@/hooks/use-appointments";
import { useCustomers } from "@/hooks/use-customers";
import { useAuthContext } from "@/lib/auth-context";
import { useEscalations } from "@/hooks/use-escalations";
import { useKbEntries } from "@/hooks/use-knowledge-base";
import { useLeads } from "@/hooks/use-leads";
import { usePending } from "@/hooks/use-pending";
import { ALERT_HREF, ALERT_LABEL } from "@/lib/alerts";

const ACTIVITY_ROWS = 6;
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

// Dashboard V2 — a from-zero greenfield redesign living on its own route,
// explicitly NOT touching `/dashboard` (see the Sprint 88 brief: "treat the
// existing dashboard as production"). Every hook below is one V1 already
// uses (or, for useCustomers, one the app already has) — no new endpoint,
// no invented field. Only the composition, visual language, and component
// set are new.
export default function DashboardV2Page() {
  const { user } = useAuthContext();
  const router = useRouter();

  const { data: pending, isPending: isLoadingPending, refetch: refetchPending } = usePending();
  const {
    data: aiActivityResult,
    isPending: isLoadingActivity,
    isError: isActivityError,
    refetch: refetchActivity,
  } = useAiActivity(ACTIVITY_ROWS);
  const { data: recentLeadsPage } = useLeads({ limit: 5 });
  const now = useMemo(() => new Date().toISOString(), []);
  const { data: upcomingAppointmentsResult, isPending: isLoadingAppointments } = useAppointments({ from: now });
  const { data: openEscalationsResult } = useEscalations({ status: "open", limit: 5 });
  const { data: analyticsDashboard } = useAnalyticsDashboard("30d");
  const { data: kbEntries } = useKbEntries();
  const { data: customersPage, isPending: isLoadingCustomers } = useCustomers({ limit: CUSTOMER_ROWS });

  const upcomingAppointments = useMemo(() => upcomingAppointmentsResult ?? [], [upcomingAppointmentsResult]);
  const aiActivity = useMemo(() => aiActivityResult ?? [], [aiActivityResult]);
  const openEscalations = useMemo(() => openEscalationsResult?.data ?? [], [openEscalationsResult]);
  const recentLeads = useMemo(() => recentLeadsPage?.data ?? [], [recentLeadsPage]);
  const customers = useMemo(() => customersPage?.data ?? [], [customersPage]);
  const learnedToday = useMemo(
    () => (kbEntries ?? []).filter((entry) => isToday(entry.created_at)),
    [kbEntries],
  );
  const healthAlerts = useMemo(
    () => analyticsDashboard?.business_health.alerts ?? [],
    [analyticsDashboard],
  );

  // The AI team roster (Business Snapshot's network visual + AI Workspace
  // panel both read from this) — real 30-day turn counts per role, sorted
  // busiest-first, zero-count roles omitted entirely rather than shown as
  // fake "idle" placeholders.
  const roster = useMemo<RosterEntry[]>(() => {
    const utilisation = analyticsDashboard?.ai_performance.employee_utilisation ?? {};
    const total = analyticsDashboard?.ai_performance.total_turns ?? 0;
    return Object.entries(utilisation)
      .filter(([, count]) => count > 0)
      .sort((a, b) => b[1] - a[1])
      .map(([role, count]) => ({
        role,
        count,
        pct: total > 0 ? Math.round((count / total) * 100) : 0,
        mostActive: role === analyticsDashboard?.ai_performance.most_used_employee,
      }));
  }, [analyticsDashboard]);

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

  const highlights = useMemo<V2Highlight[]>(() => {
    const items: V2Highlight[] = [];
    if (repliesToday > 0) {
      items.push({
        icon: CheckCheck,
        label: `${repliesToday} customer ${pluralize(repliesToday, "message", "messages")} handled`,
      });
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

  // Needs Attention's real, merged, prioritized queue — same three real
  // sources V1 merges (pending replies, open escalations, business-health
  // alerts), just reshaped into one flat AttentionItem[] instead of three
  // separately-rendered blocks. Priority is derived, not invented:
  // destructive-tone alerts + open escalations are "high" (the AI genuinely
  // can't proceed, or a human judgment call is outstanding); pending
  // replies + warning-tone alerts are "medium."
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
        reason: "Escalated — needs your judgment",
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

  return (
    <>
      <DashboardV2Hero
        name={user?.name ?? "there"}
        summary={summary}
        highlights={highlights}
        needsAttention={!attentionEmpty}
        isRefreshing={isLoadingPending || isLoadingActivity || isLoadingAppointments || isLoadingCustomers}
        onRefresh={() => {
          refetchPending();
          refetchActivity();
        }}
        pendingCount={pendingCount}
        roster={roster}
        healthData={analyticsDashboard}
      />

      {/* Zone: AI Workspace + Needs Attention — HIRA's two "what's
          happening" surfaces, asymmetric so neither reads as a filler
          match for the other. */}
      <div className="mb-10 grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-5">
          <AiTeamPanel
            roster={roster}
            avgResponseSeconds={analyticsDashboard?.overview.avg_response_time_seconds ?? null}
            escalations={analyticsDashboard?.ai_impact.human_escalations ?? 0}
            kbPublished={analyticsDashboard?.business_health.knowledge_base.published_count ?? 0}
            learnedTodayCount={learnedToday.length}
          />
        </div>
        <div className="lg:col-span-7">
          <AttentionQueue items={attentionItems} />
        </div>
      </div>

      {/* Zone: Activity Timeline — full width, one continuous narrative of
          what HIRA has actually done. Reused as-is from V1
          (dashboard-activity-timeline.tsx): already a real timeline
          (connector line, avatars, hover, outcome badges), not a component
          worth reinventing just to look different for its own sake. */}
      <div className="mb-10 rounded-2xl bg-card p-0 shadow-e2">
        <div className="flex items-center justify-between px-6 pt-6 sm:px-7 sm:pt-7">
          <h2 className="type-title">Activity timeline</h2>
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

      {/* Zone: Today's Business + Recent Customers — the other asymmetric
          pairing (5/7), so the page's rhythm never repeats a flat 50/50. */}
      <div className="mb-10 grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-5">
          <SchedulePanel appointments={upcomingAppointments} />
        </div>
        <div className="lg:col-span-7">
          <RecentCustomersPanel customers={customers} />
        </div>
      </div>

      {/* Zone: Quick actions — no data, no card chrome; a plain row on the
          page background under a hairline rule. */}
      <div className="border-t pt-6">
        <h2 className="mb-3 text-sm font-medium text-muted-foreground">Quick actions</h2>
        <div className="flex flex-wrap gap-2">
          <Button asChild size="sm" variant="outline">
            <Link href="/demo">
              <MessageSquareText />
              Test AI
            </Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href="/pending">
              <CheckCheck />
              Review replies
            </Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href="/knowledge-base">
              <BookOpen />
              Add knowledge
            </Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href="/calendar">
              <CalendarClock />
              View calendar
            </Link>
          </Button>
        </div>
      </div>
    </>
  );
}
