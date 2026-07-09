"use client";

import { Activity, AlertTriangle, CheckCheck, MessageSquare, Users } from "lucide-react";
import Link from "next/link";
import { EmptyState } from "@/components/empty-state";
import { OnboardingChecklist } from "@/components/onboarding-checklist";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useConversations } from "@/hooks/use-conversations";
import { useCustomers } from "@/hooks/use-customers";
import { useOnboardingStatus } from "@/hooks/use-onboarding";
import { usePending } from "@/hooks/use-pending";
import { describeWhatsAppConnection } from "@/lib/utils";

export default function DashboardPage() {
  const { data: pending, isLoading, isError: isPendingError, refetch: refetchPending } = usePending();
  const { data: onboarding } = useOnboardingStatus();
  // limit: 1 — only meta.total is needed here, not the rows themselves.
  const {
    data: conversations,
    isLoading: isLoadingConversations,
    isError: isConversationsError,
  } = useConversations({ limit: 1 });
  const {
    data: customers,
    isLoading: isLoadingCustomers,
    isError: isCustomersError,
  } = useCustomers({ limit: 1 });
  const whatsapp = describeWhatsAppConnection(onboarding?.business?.whatsapp_connection_status);

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Overview of your AI receptionist."
      />

      {onboarding?.business && onboarding.business.onboarding_status !== "live" && (
        <OnboardingChecklist business={onboarding.business} />
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Pending approvals"
          value={isPendingError ? "—" : (pending?.length ?? 0)}
          icon={CheckCheck}
          loading={isLoading}
          hint={isPendingError ? "Couldn't load" : "Replies awaiting review"}
        />
        <StatCard
          label="Conversations"
          value={isConversationsError ? "—" : (conversations?.meta.total ?? 0)}
          icon={MessageSquare}
          loading={isLoadingConversations}
          hint={isConversationsError ? "Couldn't load" : "Total conversations"}
        />
        <StatCard
          label="Customers"
          value={isCustomersError ? "—" : (customers?.meta.total ?? 0)}
          icon={Users}
          loading={isLoadingCustomers}
          hint={isCustomersError ? "Couldn't load" : "People who have messaged you"}
        />
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
                className="py-10"
              />
            ) : (pending?.length ?? 0) === 0 ? (
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
            <StatusRow
              label="WhatsApp integration"
              ok={onboarding?.business?.whatsapp_connection_status === "connected"}
              note={whatsapp.label}
              variant={whatsapp.variant}
            />
          </CardContent>
        </Card>
      </div>
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
