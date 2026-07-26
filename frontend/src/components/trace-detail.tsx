"use client";

import { AlertTriangle, ArrowLeft, Bot, ListTree, MessageSquare, Wrench } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useFounderTraceDetail } from "@/hooks/use-founder-ops";
import type { TraceOutcome } from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";

const ROLE_LABEL: Record<string, string> = {
  receptionist: "Receptionist",
  scheduler: "Scheduler",
  sales_executive: "Sales Executive",
  bookkeeper: "Bookkeeper",
};

function roleLabel(role: string): string {
  return ROLE_LABEL[role] ?? role;
}

const OUTCOME_BADGE: Record<TraceOutcome, { label: string; variant: BadgeProps["variant"] }> = {
  sent: { label: "Sent", variant: "success" },
  pending_approval: { label: "Pending approval", variant: "warning" },
  sending: { label: "Sending", variant: "secondary" },
  failed: { label: "Failed", variant: "destructive" },
  rejected: { label: "Rejected", variant: "destructive" },
  escalated: { label: "Escalated", variant: "warning" },
  no_result: { label: "No result", variant: "secondary" },
};

// Sprint 76, Objective C: Conversation Replay — read-only inspection of one
// customer turn's execution. No editing anywhere in this component; every
// figure shown is either the write-once trace itself or the current state
// of the Message rows it produced (see app/services/execution_traces.py).
export function TraceDetailPane({
  traceId,
  onBack,
}: {
  traceId: string | null;
  onBack: () => void;
}) {
  const { data: trace, isLoading, isError, refetch } = useFounderTraceDetail(traceId);

  if (traceId === null) {
    return (
      <Card className="hidden min-h-[420px] lg:flex">
        <CardContent className="flex w-full items-center justify-center p-6">
          <EmptyState
            icon={ListTree}
            title="No execution selected"
            description="Select a turn to replay its execution plan, employee sequence, and outcome."
            className="border-0"
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex items-center gap-3 border-b px-4 py-3">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            aria-label="Back to executions"
            onClick={onBack}
          >
            <ArrowLeft />
          </Button>
          {isLoading && <Skeleton className="h-5 w-40" />}
          {isError && (
            <EmptyState
              icon={AlertTriangle}
              title="Couldn't load this execution"
              action={
                <Button size="sm" onClick={() => refetch()}>
                  Retry
                </Button>
              }
              className="border-0 py-4"
            />
          )}
          {!isLoading && !isError && trace && (
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="truncate text-sm font-medium">
                  {trace.business_name ?? "Unknown business"}
                </p>
                <Badge variant={OUTCOME_BADGE[trace.outcome].variant}>
                  {OUTCOME_BADGE[trace.outcome].label}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                {formatRelativeTime(trace.created_at)} · {trace.duration_ms}ms · {trace.category}
              </p>
            </div>
          )}
        </div>
      </Card>

      {!isLoading && !isError && trace && (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <MessageSquare className="size-4" /> Customer message
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                {trace.customer_message ?? "No customer message recorded for this turn."}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <ListTree className="size-4" /> Execution plan
              </CardTitle>
            </CardHeader>
            <CardContent>
              {trace.plan.steps.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  {trace.plan.clarification_hint ?? "No tools were offered for this turn."}
                </p>
              ) : (
                <ol className="space-y-3">
                  {trace.plan.steps.map((step, i) => (
                    <li key={`${step.domain}-${i}`} className="flex items-start gap-3">
                      <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
                        {i + 1}
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm font-medium">
                          {step.role ? roleLabel(step.role) : "Unassigned"}
                          <span className="ml-2 font-normal text-muted-foreground">
                            {step.domain}
                            {step.action ? ` · ${step.action}` : ""}
                          </span>
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Offered: {step.tools.join(", ")}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
              {trace.plan.clarification_hint && trace.plan.steps.length > 0 && (
                <p className="mt-3 border-t pt-3 text-xs text-muted-foreground">
                  Stopped early: {trace.plan.clarification_hint}
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <Wrench className="size-4" /> Tool execution
              </CardTitle>
            </CardHeader>
            <CardContent>
              {trace.proposed_tool_calls.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No tool call was proposed this turn.
                </p>
              ) : (
                <ul className="space-y-2">
                  {trace.proposed_tool_calls.map((call, i) => (
                    <li key={i} className="flex items-center justify-between gap-2 text-sm">
                      <span className="font-mono text-xs">{call.tool_name}</span>
                      {call.agent_role && (
                        <Badge variant="secondary">{roleLabel(call.agent_role)}</Badge>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <Bot className="size-4" /> Final response
              </CardTitle>
            </CardHeader>
            <CardContent>
              {trace.result_messages.length === 0 ? (
                <p className="text-sm text-muted-foreground">This turn produced no message.</p>
              ) : (
                <ul className="space-y-3">
                  {trace.result_messages.map((message) => (
                    <li key={message.id} className="rounded-md border p-3">
                      <div className="mb-1 flex items-center justify-between gap-2">
                        <Badge variant="outline" className="text-xs">
                          {message.type}
                        </Badge>
                        <span className="text-xs capitalize text-muted-foreground">
                          {message.status.replace("_", " ")}
                        </span>
                      </div>
                      <p className="whitespace-pre-wrap text-sm">{message.body}</p>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
