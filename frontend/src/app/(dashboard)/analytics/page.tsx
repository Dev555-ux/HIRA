"use client";

import { BarChart3, Clock, MessageSquare, CheckCheck } from "lucide-react";
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
              <div className="flex h-48 items-end gap-2">
                {[40, 65, 30, 80, 55, 70, 45].map((h, i) => (
                  <div
                    key={i}
                    className="flex-1 rounded-t bg-muted"
                    style={{ height: `${h}%` }}
                    aria-hidden
                  />
                ))}
              </div>
              <p className="mt-3 text-xs text-muted-foreground">
                Placeholder chart — live data lands with the analytics API.
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
