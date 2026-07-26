"use client";

import { AlertTriangle, CheckCheck, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { PendingReplyCard } from "@/components/pending-reply-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { usePending } from "@/hooks/use-pending";

export default function PendingPage() {
  const { data, isPending, isError, error, isFetching, refetch } = usePending();

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

      {isPending && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      )}

      {isError && (
        <EmptyState
          icon={AlertTriangle}
          title="Couldn't load pending replies"
          description={(error as Error).message}
          action={
            <Button size="sm" onClick={() => refetch()}>
              Retry
            </Button>
          }
        />
      )}

      {!isPending && !isError && data && data.length === 0 && (
        <EmptyState
          icon={CheckCheck}
          title="All caught up"
          description="There are no replies waiting for approval right now."
        />
      )}

      {!isPending && !isError && data && data.length > 0 && (
        <div className="space-y-3">
          {data.map((reply) => (
            <PendingReplyCard key={reply.id} reply={reply} />
          ))}
        </div>
      )}
    </>
  );
}
