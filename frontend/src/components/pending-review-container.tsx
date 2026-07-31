"use client";

import { ReviewReplyCard, type ReviewStatus } from "@/components/review-reply-card";
import { useToast } from "@/components/ui/toast";
import { usePendingReplyActions } from "@/hooks/use-conversations";
import type { Message } from "@/lib/types";

// Integration layer (PR5): maps a pending_approval Message + the existing
// conversation-scoped mutations onto the presentation-only ReviewReplyCard.
//
//   PendingReviewContainer → maps backend data → ReviewReplyCard
//
// The card owns no fetching, no cache, no backend awareness — all of that lives
// here. groundedCount/confidence are deliberately NOT passed: the conversation
// messages API exposes neither (no ai_meta on Message), so nothing is fabricated.

function reviewStatus(message: Message, approving: boolean): ReviewStatus {
  if (approving) return "sending";
  switch (message.status) {
    case "sending":
      return "sending";
    case "sent":
      return "sent";
    case "escalated":
      return "escalated";
    case "failed":
      return "error";
    default:
      return "waiting"; // pending_approval
  }
}

export function PendingReviewContainer({ message }: { message: Message }) {
  const { approve, reject, edit } = usePendingReplyActions();
  const { toast } = useToast();

  const pending = approve.isPending || reject.isPending || edit.isPending;

  // On failure the action didn't take, so the reply stays awaiting review and
  // the controls re-enable for a retry — the existing destructive-toast pattern
  // surfaces what went wrong. (Existing loading/error patterns; no new UI.)
  const onError = (action: string) => () =>
    toast({ title: `Couldn't ${action} the reply`, description: "Please try again.", variant: "destructive" });

  return (
    <ReviewReplyCard
      body={message.body}
      status={reviewStatus(message, approve.isPending)}
      pending={pending}
      onApprove={() => approve.mutate(message.id, { onError: onError("approve") })}
      onReject={() => reject.mutate(message.id, { onError: onError("reject") })}
      onEdit={(nextBody) =>
        edit.mutate({ messageId: message.id, body: nextBody }, { onError: onError("save") })
      }
    />
  );
}
