"use client";

import { AlertTriangle, CheckCheck, RefreshCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { PendingReplyCard, type PendingReplyCardHandle } from "@/components/pending-reply-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { usePending } from "@/hooks/use-pending";

// IMPLEMENTATION-ROADMAP-001 M12: the review queue's keyboard shortcuts
// (DESIGN-SCREENBOOK-001 §14) — j/k move the active card, Enter approves it,
// e focuses its editor, x rejects it. Lives at the page/list level (not per-
// card) since "next/previous" is a list concept, and dispatches into each
// card's own PendingReplyCardHandle rather than duplicating any mutation
// logic here.
export default function PendingPage() {
  const { data, isPending, isError, error, isFetching, refetch } = usePending();
  const [activeIndex, setActiveIndex] = useState(0);
  const cardRefs = useRef<(PendingReplyCardHandle | null)[]>([]);

  const replies = data ?? [];

  // Keep the active index in range as the list shrinks/grows (an approve or
  // reject removes a row via the existing optimistic PENDING_KEY update).
  useEffect(() => {
    setActiveIndex((i) => Math.min(i, Math.max(replies.length - 1, 0)));
  }, [replies.length]);

  useEffect(() => {
    if (replies.length === 0) return;

    function onKeyDown(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      // Never hijack j/k/e/x while the operator is actually typing them into
      // a draft — only bare, unmodified letter/Enter presses outside any
      // editable field count as a shortcut.
      const isEditable =
        target instanceof HTMLElement &&
        (target.tagName === "TEXTAREA" ||
          target.tagName === "INPUT" ||
          target.isContentEditable);
      if (isEditable || e.metaKey || e.ctrlKey || e.altKey) return;

      const card = cardRefs.current[activeIndex];
      switch (e.key) {
        case "j":
          e.preventDefault();
          setActiveIndex((i) => Math.min(i + 1, replies.length - 1));
          break;
        case "k":
          e.preventDefault();
          setActiveIndex((i) => Math.max(i - 1, 0));
          break;
        case "Enter":
          e.preventDefault();
          card?.approve();
          break;
        case "e":
          e.preventDefault();
          card?.focusEditor();
          break;
        case "x":
          e.preventDefault();
          card?.reject();
          break;
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [activeIndex, replies.length]);

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

      {!isPending && !isError && replies.length === 0 && (
        <EmptyState
          icon={CheckCheck}
          title="All caught up"
          description="There are no replies waiting for approval right now."
        />
      )}

      {!isPending && !isError && replies.length > 0 && (
        <>
          <p className="mb-3 text-xs text-muted-foreground">
            Keyboard: <kbd className="rounded border px-1 py-0.5 font-mono">j</kbd>/
            <kbd className="rounded border px-1 py-0.5 font-mono">k</kbd> to move,{" "}
            <kbd className="rounded border px-1 py-0.5 font-mono">⏎</kbd> to approve,{" "}
            <kbd className="rounded border px-1 py-0.5 font-mono">e</kbd> to edit,{" "}
            <kbd className="rounded border px-1 py-0.5 font-mono">x</kbd> to reject.
          </p>
          <div className="space-y-3">
            {replies.map((reply, i) => (
              <PendingReplyCard
                key={reply.id}
                ref={(el) => {
                  cardRefs.current[i] = el;
                }}
                reply={reply}
                active={i === activeIndex}
              />
            ))}
          </div>
        </>
      )}
    </>
  );
}
