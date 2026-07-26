"use client";

import { BarChart3, Clock, MessageSquare, CheckCheck } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useConversations } from "@/hooks/use-conversations";
import { usePending } from "@/hooks/use-pending";

export default function AnalyticsPage() {
  const { data: pending, isPending, isError: isPendingError } = usePending();
  // limit: 1 — only meta.total is needed here, not the rows themselves. Same
  // data /dashboard already shows live (Sprint 32) — this tile showed a fake
  // "Coming soon" for it too until Sprint 35's audit caught the inconsistency.
  const { data: conversations, isPending: isPendingConversations, isError: isConversationsError } =
    useConversations({ limit: 1 });

  return (
    <>
      <PageHeader title="Analytics" description="How your AI employee is performing." />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total conversations"
          value={isConversationsError ? "—" : (conversations?.meta.total ?? 0)}
          icon={MessageSquare}
          loading={isPendingConversations}
          hint={isConversationsError ? "Couldn't load" : undefined}
        />
        <StatCard label="Messages today" value="—" icon={BarChart3} hint="Coming soon" />
        <StatCard
          label="Pending approvals"
          value={isPendingError ? "—" : (pending?.length ?? 0)}
          icon={CheckCheck}
          loading={isPending}
          hint={isPendingError ? "Couldn't load" : undefined}
        />
        <StatCard label="Avg response time" value="—" icon={Clock} hint="Coming soon" />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        {["Conversations over time", "Messages by day"].map((title) => (
          <Card key={title}>
            <CardHeader>
              <CardTitle className="text-base">{title}</CardTitle>
            </CardHeader>
            <CardContent>
              <EmptyState
                icon={BarChart3}
                title="Analytics coming soon"
                description="This chart will appear here once conversation data is available."
                className="border-0 py-10"
              />
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
