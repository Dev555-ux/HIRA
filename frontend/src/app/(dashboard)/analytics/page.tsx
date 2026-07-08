"use client";

import { BarChart3, Clock, MessageSquare, CheckCheck } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePending } from "@/hooks/use-pending";

export default function AnalyticsPage() {
  const { data: pending, isLoading } = usePending();

  return (
    <>
      <PageHeader title="Analytics" description="How your AI receptionist is performing." />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total conversations" value="—" icon={MessageSquare} hint="Coming soon" />
        <StatCard label="Messages today" value="—" icon={BarChart3} hint="Coming soon" />
        <StatCard
          label="Pending approvals"
          value={pending?.length ?? 0}
          icon={CheckCheck}
          loading={isLoading}
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
