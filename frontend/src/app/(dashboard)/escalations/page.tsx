"use client";

import { AlertTriangle, ArrowRight, CheckCircle2, RefreshCw, UserMinus, UserPlus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useAssignEscalation,
  useEscalations,
  useResolveEscalation,
  useUnassignEscalation,
} from "@/hooks/use-escalations";
import { useAuthContext } from "@/lib/auth-context";
import type {
  Escalation,
  EscalationAssignedFilter,
  EscalationReason,
  EscalationStatusFilter,
} from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";

const STATUS_FILTERS: { label: string; value: EscalationStatusFilter | undefined }[] = [
  { label: "Open", value: "open" },
  { label: "Resolved", value: "resolved" },
  { label: "All", value: undefined },
];

const ASSIGNED_FILTERS: { label: string; value: EscalationAssignedFilter | undefined }[] = [
  { label: "All", value: undefined },
  { label: "Unassigned", value: "unassigned" },
  { label: "Mine", value: "mine" },
];

const REASON_LABEL: Record<EscalationReason, string> = {
  low_confidence: "AI wasn't confident",
  customer_request: "Customer asked for a human",
  external_failure: "Message failed to send",
  other: "Other",
};

export default function EscalationsPage() {
  const [statusFilter, setStatusFilter] = useState<EscalationStatusFilter | undefined>("open");
  const [assignedFilter, setAssignedFilter] = useState<EscalationAssignedFilter | undefined>(
    undefined,
  );

  const { data, isLoading, isError, error, isFetching, refetch } = useEscalations({
    status: statusFilter,
    assigned: assignedFilter,
  });
  const escalations = data?.data ?? [];

  return (
    <>
      <PageHeader
        title="Escalations"
        description="Conversations that need a human — assign, resolve, and jump straight to the thread."
        action={
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className={isFetching ? "animate-spin" : ""} />
            Refresh
          </Button>
        }
      />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-1">
          {STATUS_FILTERS.map((f) => (
            <Button
              key={f.label}
              size="sm"
              variant={statusFilter === f.value ? "secondary" : "ghost"}
              onClick={() => setStatusFilter(f.value)}
            >
              {f.label}
            </Button>
          ))}
        </div>
        <div className="flex gap-1">
          {ASSIGNED_FILTERS.map((f) => (
            <Button
              key={f.label}
              size="sm"
              variant={assignedFilter === f.value ? "secondary" : "ghost"}
              onClick={() => setAssignedFilter(f.value)}
            >
              {f.label}
            </Button>
          ))}
        </div>
      </div>

      {isLoading && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      )}

      {isError && (
        <EmptyState
          icon={AlertTriangle}
          title="Couldn't load escalations"
          description={error instanceof Error ? error.message : "Something went wrong."}
          action={
            <Button size="sm" onClick={() => refetch()}>
              Retry
            </Button>
          }
        />
      )}

      {!isLoading && !isError && escalations.length === 0 && (
        <EmptyState
          icon={CheckCircle2}
          title="Nothing needs you right now"
          description="Escalated conversations — low-confidence AI replies, customer requests for a human, or failed sends — will show up here."
        />
      )}

      {!isLoading && !isError && escalations.length > 0 && (
        <div className="space-y-3">
          {escalations.map((escalation) => (
            <EscalationCard key={escalation.id} escalation={escalation} />
          ))}
        </div>
      )}
    </>
  );
}

function EscalationCard({ escalation }: { escalation: Escalation }) {
  const { user } = useAuthContext();
  const { toast } = useToast();
  const assign = useAssignEscalation();
  const unassign = useUnassignEscalation();
  const resolve = useResolveEscalation();

  const name = escalation.conversation.customer.display_name || escalation.conversation.customer.wa_phone;
  const isMine = escalation.assigned_to?.email === user?.email;

  async function handleResolve() {
    await resolve.mutateAsync(escalation.id);
    toast({ title: "Resolved.", variant: "success" });
  }

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium">{name}</span>
            {escalation.status === "resolved" ? (
              <Badge variant="secondary">Resolved</Badge>
            ) : (
              <Badge variant="warning">{REASON_LABEL[escalation.reason]}</Badge>
            )}
            {escalation.assigned_to && (
              <Badge variant="outline">
                {isMine ? "Assigned to you" : `Assigned to ${escalation.assigned_to.email}`}
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            Escalated {formatRelativeTime(escalation.created_at)}
          </p>
        </div>

        <div className="flex shrink-0 flex-wrap gap-2">
          <Button asChild size="sm" variant="outline">
            <Link href={`/inbox?conversation=${escalation.conversation.id}`}>
              Open conversation <ArrowRight />
            </Link>
          </Button>
          {escalation.status === "open" && (
            <>
              {escalation.assigned_to ? (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => unassign.mutate(escalation.id)}
                  disabled={unassign.isPending}
                >
                  <UserMinus /> Unassign
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => assign.mutate(escalation.id)}
                  disabled={assign.isPending}
                >
                  <UserPlus /> Assign to me
                </Button>
              )}
              <Button size="sm" onClick={handleResolve} disabled={resolve.isPending}>
                <CheckCircle2 /> Resolve
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
