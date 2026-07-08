"use client";

import { CheckCheck, RefreshCw, Send, X } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApprove, usePending } from "@/hooks/use-pending";
import { formatRelativeTime } from "@/lib/utils";

export default function PendingPage() {
  const { data, isLoading, isError, error, isFetching, refetch } = usePending();
  const approve = useApprove();

  return (
    <>
      <PageHeader
        title="Pending Replies"
        description="AI-drafted replies awaiting your approval (Assisted Mode)."
        action={
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className={isFetching ? "animate-spin" : ""} />
            Refresh
          </Button>
        }
      />

      {isLoading && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      )}

      {isError && (
        <EmptyState
          icon={X}
          title="Couldn't load pending replies"
          description={(error as Error).message}
          action={
            <Button size="sm" onClick={() => refetch()}>
              Retry
            </Button>
          }
        />
      )}

      {!isLoading && !isError && data && data.length === 0 && (
        <EmptyState
          icon={CheckCheck}
          title="All caught up"
          description="There are no replies waiting for approval right now."
        />
      )}

      {!isLoading && !isError && data && data.length > 0 && (
        <div className="space-y-3">
          {data.map((reply) => (
            <Card key={reply.id}>
              <CardContent className="p-5">
                <div className="mb-3 flex items-center justify-between">
                  <Badge variant="warning">Pending approval</Badge>
                  <span className="text-xs text-muted-foreground">
                    {formatRelativeTime(reply.created_at)}
                  </span>
                </div>
                <p className="text-sm leading-relaxed">{reply.body}</p>
                <div className="mt-4 flex gap-2">
                  <Button
                    size="sm"
                    disabled={approve.isPending}
                    onClick={() => approve.mutate(reply.id)}
                  >
                    <Send /> Approve &amp; send
                  </Button>
                  <Button size="sm" variant="outline" disabled title="Rejecting replies is coming soon">
                    <X /> Reject
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
