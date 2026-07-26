"use client";

import { AlertTriangle, ArrowLeft, ListTree } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { TraceDetailPane } from "@/components/trace-detail";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useFounderTraces } from "@/hooks/use-founder-ops";
import type { FounderTraceRow, TraceOutcome } from "@/lib/types";
import { cn, formatRelativeTime } from "@/lib/utils";

const PAGE_SIZE = 20;

const OUTCOME_BADGE: Record<TraceOutcome, { label: string; variant: BadgeProps["variant"] }> = {
  sent: { label: "Sent", variant: "success" },
  pending_approval: { label: "Pending", variant: "warning" },
  sending: { label: "Sending", variant: "secondary" },
  failed: { label: "Failed", variant: "destructive" },
  rejected: { label: "Rejected", variant: "destructive" },
  escalated: { label: "Escalated", variant: "warning" },
  no_result: { label: "No result", variant: "secondary" },
};

const ROLE_LABEL: Record<string, string> = {
  receptionist: "Receptionist",
  scheduler: "Scheduler",
  sales_executive: "Sales Executive",
  bookkeeper: "Bookkeeper",
};

// Sprint 76, Objective C: Conversation Replay list. Same master-detail
// layout as /customers and /leads — one page, no per-record route, a
// selected id drives which pane shows on mobile (see TraceDetailPane).
export default function FounderTracesPage() {
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data, isPending, isError, refetch } = useFounderTraces({
    limit: PAGE_SIZE,
    offset,
  });
  const traces = data ?? [];

  return (
    <>
      <PageHeader
        title="AI Execution Log"
        description="Every customer turn HIRA's AI Employees have executed — read-only."
        action={
          <Button variant="outline" size="sm" asChild>
            <Link href="/ops">
              <ArrowLeft />
              Back to overview
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[420px_1fr]">
        <TraceList
          traces={traces}
          isPending={isPending}
          isError={isError}
          onRetry={refetch}
          selectedId={selectedId}
          onSelect={setSelectedId}
          offset={offset}
          pageSize={PAGE_SIZE}
          onOffsetChange={setOffset}
        />
        <TraceDetailPane traceId={selectedId} onBack={() => setSelectedId(null)} />
      </div>
    </>
  );
}

function TraceList({
  traces,
  isPending,
  isError,
  onRetry,
  selectedId,
  onSelect,
  offset,
  pageSize,
  onOffsetChange,
}: {
  traces: FounderTraceRow[];
  isPending: boolean;
  isError: boolean;
  onRetry: () => void;
  selectedId: string | null;
  onSelect: (id: string) => void;
  offset: number;
  pageSize: number;
  onOffsetChange: (offset: number) => void;
}) {
  return (
    <Card
      className={cn("flex min-h-[420px] flex-col", selectedId !== null ? "hidden lg:flex" : "flex")}
    >
      <CardContent className="flex-1 p-0">
        {isPending && (
          <div className="space-y-3 p-4">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        )}

        {isError && (
          <EmptyState
            icon={AlertTriangle}
            title="Couldn't load executions"
            action={
              <Button size="sm" onClick={onRetry}>
                Retry
              </Button>
            }
            className="border-0 py-16"
          />
        )}

        {!isPending && !isError && traces.length === 0 && (
          <EmptyState
            icon={ListTree}
            title="No executions yet"
            description="Traced turns will appear here once customers start messaging."
            className="border-0 py-16"
          />
        )}

        {!isPending && !isError && traces.length > 0 && (
          <ul className="divide-y">
            {traces.map((trace) => (
              <li key={trace.id}>
                <button
                  type="button"
                  onClick={() => onSelect(trace.id)}
                  className={cn(
                    "flex w-full flex-col gap-1 px-4 py-3 text-left transition-colors hover:bg-accent/50",
                    selectedId === trace.id && "bg-accent",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium">
                      {trace.business_name ?? "Unknown business"}
                    </span>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {formatRelativeTime(trace.created_at)}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge variant={OUTCOME_BADGE[trace.outcome].variant}>
                      {OUTCOME_BADGE[trace.outcome].label}
                    </Badge>
                    {trace.roles.map((role, i) => (
                      <Badge key={`${role}-${i}`} variant="secondary">
                        {ROLE_LABEL[role] ?? role}
                      </Badge>
                    ))}
                    {trace.roles.length === 0 && (
                      <span className="text-xs text-muted-foreground">{trace.category}</span>
                    )}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>

      <div className="flex items-center justify-between border-t px-4 py-3 text-xs text-muted-foreground">
        <span>
          {traces.length === 0 ? "0" : `${offset + 1}–${offset + traces.length}`}
        </span>
        <div className="flex gap-1">
          <Button
            variant="outline"
            size="sm"
            disabled={offset === 0}
            onClick={() => onOffsetChange(Math.max(0, offset - pageSize))}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={traces.length < pageSize}
            onClick={() => onOffsetChange(offset + pageSize)}
          >
            Next
          </Button>
        </div>
      </div>
    </Card>
  );
}
