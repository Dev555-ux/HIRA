"use client";

import { AlertTriangle, ArrowRight, CheckCircle2, RefreshCw, UserMinus, UserPlus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import type { ActivityState } from "@/components/ui/activity-dot";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { StatusPill } from "@/components/ui/status-pill";
import { useToast } from "@/components/ui/toast";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useAssignEscalation,
  useEscalations,
  useResolveEscalation,
  useUnassignEscalation,
} from "@/hooks/use-escalations";
import { ApiError } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import { REASON_LABEL } from "@/lib/escalations";
import type { Escalation, EscalationAssignedFilter, EscalationStatusFilter } from "@/lib/types";
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

// M8: StatusPill's status→dot-color mapping, single consumer (this file),
// so kept local rather than a new lib/escalations.ts. Preserves today's
// exact colors: open used the amber "warning" Badge, resolved used the
// neutral "secondary" one (never green/success — closing an escalation
// isn't a celebratory outcome here, it's just no-longer-active).
const ESCALATION_STATUS_STATE: Record<Escalation["status"], ActivityState> = {
  open: "waiting",
  resolved: "idle",
};

export default function EscalationsPage() {
  const [statusFilter, setStatusFilter] = useState<EscalationStatusFilter | undefined>("open");
  const [assignedFilter, setAssignedFilter] = useState<EscalationAssignedFilter | undefined>(
    undefined,
  );

  const { data, isPending, isError, error, isFetching, refetch } = useEscalations({
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

      {isPending && (
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

      {!isPending && !isError && escalations.length === 0 && (
        <EmptyState
          icon={CheckCircle2}
          title="Nothing needs you right now"
          description="Escalated conversations — low-confidence AI replies, customer requests for a human, or failed sends — will show up here."
        />
      )}

      {!isPending && !isError && escalations.length > 0 && (
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
    try {
      await resolve.mutateAsync(escalation.id);
      toast({ title: "Resolved.", variant: "success" });
    } catch (err) {
      toast({
        title: "Couldn't resolve this escalation",
        description: err instanceof ApiError ? err.message : "Something went wrong — please try again.",
        variant: "destructive",
      });
    }
  }

  function handleAssign() {
    assign.mutate(escalation.id, {
      onError: (err) => {
        toast({
          title: "Couldn't assign this escalation",
          description: err instanceof ApiError ? err.message : "Something went wrong — please try again.",
          variant: "destructive",
        });
      },
    });
  }

  function handleUnassign() {
    unassign.mutate(escalation.id, {
      onError: (err) => {
        toast({
          title: "Couldn't unassign this escalation",
          description: err instanceof ApiError ? err.message : "Something went wrong — please try again.",
          variant: "destructive",
        });
      },
    });
  }

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium">{name}</span>
            <StatusPill state={ESCALATION_STATUS_STATE[escalation.status]}>
              {escalation.status === "resolved" ? "Resolved" : REASON_LABEL[escalation.reason]}
            </StatusPill>
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
                  onClick={handleUnassign}
                  disabled={unassign.isPending}
                >
                  <UserMinus /> Unassign
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleAssign}
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
