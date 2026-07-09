"use client";

import { Flag, RefreshCw, Send, X } from "lucide-react";
import { useEffect, useState } from "react";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  useApprove,
  useEscalate,
  useRegenerate,
  useReject,
  useUpdateDraft,
} from "@/hooks/use-pending";
import { ApiError } from "@/lib/api";
import { MAX_DRAFT_LENGTH } from "@/lib/config";
import type { PendingReply } from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";

type ConfirmableAction = "regenerate" | "reject" | "escalate";

const CONFIRM_COPY: Record<
  ConfirmableAction,
  { title: string; description: string; confirmLabel: string }
> = {
  regenerate: {
    title: "Discard your edits?",
    description:
      "Regenerating replaces your edited draft with a new AI-written reply. Your edits will be lost.",
    confirmLabel: "Discard & regenerate",
  },
  reject: {
    title: "Discard your edits?",
    description: "Rejecting this reply discards your edits — it will not be sent to the customer.",
    confirmLabel: "Discard & reject",
  },
  escalate: {
    title: "Discard your edits?",
    description:
      "Escalating discards your edits and hands this conversation to a teammate.",
    confirmLabel: "Discard & escalate",
  },
};

function errorMessage(err: unknown): string {
  return err instanceof ApiError ? err.message : "Something went wrong — please try again.";
}

export function PendingReplyCard({ reply }: { reply: PendingReply }) {
  const { toast } = useToast();
  const approve = useApprove();
  const updateDraft = useUpdateDraft();
  const reject = useReject();
  const regenerate = useRegenerate();
  const escalate = useEscalate();

  // Same "local override synced from server data" pattern as Settings'
  // AiReplyModeCard: null means "show the server value," a string means the
  // operator has typed something that hasn't been saved yet.
  const [draftOverride, setDraftOverride] = useState<string | null>(null);
  const [confirmAction, setConfirmAction] = useState<ConfirmableAction | null>(null);

  useEffect(() => {
    setDraftOverride(null);
  }, [reply.body]);

  const draft = draftOverride ?? reply.body;
  const isDirty = draftOverride !== null && draftOverride !== reply.body;
  const isEmpty = draft.trim().length === 0;
  const isBusy =
    approve.isPending ||
    updateDraft.isPending ||
    reject.isPending ||
    regenerate.isPending ||
    escalate.isPending;

  async function handleApprove() {
    try {
      if (isDirty) {
        await updateDraft.mutateAsync({ id: reply.id, body: draft.trim() });
      }
      await approve.mutateAsync(reply.id);
      toast({
        title: "Reply sent",
        description: "The customer will receive it shortly.",
        variant: "success",
      });
    } catch (err) {
      toast({ title: "Couldn't send reply", description: errorMessage(err), variant: "destructive" });
    }
  }

  function requestAction(action: ConfirmableAction) {
    if (isDirty) {
      setConfirmAction(action);
    } else {
      runAction(action);
    }
  }

  async function runAction(action: ConfirmableAction) {
    setConfirmAction(null);
    try {
      if (action === "regenerate") {
        await regenerate.mutateAsync(reply.id);
        toast({ title: "Draft regenerated", variant: "success" });
      } else if (action === "reject") {
        await reject.mutateAsync(reply.id);
        toast({
          title: "Reply rejected",
          description: "It will not be sent to the customer.",
        });
      } else {
        await escalate.mutateAsync(reply.id);
        toast({
          title: "Escalated to a human",
          description: "A teammate will take it from here.",
        });
      }
    } catch (err) {
      const label = action === "regenerate" ? "regenerate draft" : `${action} reply`;
      toast({ title: `Couldn't ${label}`, description: errorMessage(err), variant: "destructive" });
    }
  }

  const customerName = reply.customer?.display_name?.trim() || reply.customer?.wa_phone;

  return (
    <Card>
      <CardContent className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold">{customerName ?? "Unknown customer"}</p>
            {reply.customer?.display_name && (
              <p className="text-xs text-muted-foreground">{reply.customer.wa_phone}</p>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Badge variant="warning">Pending approval</Badge>
            <span className="text-xs text-muted-foreground">
              {formatRelativeTime(reply.created_at)}
            </span>
          </div>
        </div>

        {reply.conversation_preview && (
          <div className="rounded-md bg-muted/50 p-3">
            <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Customer said
            </p>
            <p className="line-clamp-2 text-sm text-muted-foreground">
              {reply.conversation_preview}
            </p>
          </div>
        )}

        <div className="space-y-1.5">
          <Textarea
            value={draft}
            onChange={(e) => setDraftOverride(e.target.value)}
            disabled={isBusy}
            maxLength={MAX_DRAFT_LENGTH}
            rows={4}
            aria-label="AI-drafted reply"
            className="text-sm leading-relaxed"
          />
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{isDirty ? "Edited — not yet saved" : "AI draft"}</span>
            <span>
              {draft.length} / {MAX_DRAFT_LENGTH}
            </span>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button size="sm" disabled={isBusy || isEmpty} onClick={handleApprove}>
            <Send />
            {updateDraft.isPending
              ? "Saving…"
              : approve.isPending
                ? "Sending…"
                : "Approve & send"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={isBusy}
            onClick={() => requestAction("regenerate")}
          >
            <RefreshCw className={regenerate.isPending ? "animate-spin" : ""} />
            Regenerate
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={isBusy}
            onClick={() => requestAction("reject")}
          >
            <X />
            Reject
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={isBusy}
            onClick={() => requestAction("escalate")}
          >
            <Flag />
            Escalate
          </Button>
        </div>
      </CardContent>

      <ConfirmDialog
        open={confirmAction !== null}
        onOpenChange={(open) => !open && setConfirmAction(null)}
        title={confirmAction ? CONFIRM_COPY[confirmAction].title : ""}
        description={confirmAction ? CONFIRM_COPY[confirmAction].description : undefined}
        confirmLabel={confirmAction ? CONFIRM_COPY[confirmAction].confirmLabel : "Confirm"}
        onConfirm={() => confirmAction && runAction(confirmAction)}
        isPending={isBusy}
      />
    </Card>
  );
}
