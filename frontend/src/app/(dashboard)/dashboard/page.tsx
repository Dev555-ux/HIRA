"use client";

import { Activity, CheckCheck, MessageSquare, Users } from "lucide-react";
import Link from "next/link";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePending } from "@/hooks/use-pending";

export default function DashboardPage() {
  const { data: pending, isLoading } = usePending();

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Overview of your AI receptionist."
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Pending approvals"
          value={pending?.length ?? 0}
          icon={CheckCheck}
          loading={isLoading}
          hint="Replies awaiting review"
        />
        <StatCard label="Conversations" value="—" icon={MessageSquare} hint="Endpoint coming soon" />
        <StatCard label="Customers" value="—" icon={Users} hint="Endpoint coming soon" />
        <StatCard label="AI activity" value="Live" icon={Activity} hint="Groq · llama-3.3-70b" />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="text-base">Pending approvals</CardTitle>
            <Button asChild size="sm" variant="ghost">
              <Link href="/pending">View all</Link>
            </Button>
          </CardHeader>
          <CardContent>
            {(pending?.length ?? 0) === 0 ? (
              <EmptyState
                icon={CheckCheck}
                title="Nothing pending"
                description="AI replies awaiting approval will appear here."
                className="py-10"
              />
            ) : (
              <ul className="space-y-3">
                {pending!.slice(0, 4).map((p) => (
                  <li key={p.id} className="flex items-start justify-between gap-3">
                    <p className="line-clamp-2 text-sm text-muted-foreground">{p.body}</p>
                    <Badge variant="warning">pending</Badge>
                  </li>
                ))}
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
            <StatusRow label="WhatsApp integration" ok={false} note="Paused — awaiting number" />
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function StatusRow({ label, ok, note }: { label: string; ok: boolean; note?: string }) {
  return (
    <div className="flex items-center justify-between">
      <span>{label}</span>
      <Badge variant={ok ? "success" : "secondary"}>{note ?? (ok ? "Operational" : "Off")}</Badge>
    </div>
  );
}
