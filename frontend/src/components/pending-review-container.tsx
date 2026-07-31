"use client";

import { ReviewReplyCard, type ReviewStatus } from "@/components/review-reply-card";
import { useToast } from "@/components/ui/toast";
import { usePendingReplyActions } from "@/hooks/use-conversations";
import type { Message } from "@/lib/types";

// Integration layer: maps a pending_approval Message + its backend review
// metadata + the existing conversation-scoped mutations onto the presentation-
// only ReviewReplyCard.
//
//   PendingReviewContainer → maps backend data → ReviewReplyCard
//
// The card owns no fetching, no cache, no backend awareness — all of that lives
// here. review metadata (confidence / grounding / generation_status) is passed
// through only when the backend actually provides it; older payloads without
// `review` degrade to exactly the prior behaviour.

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

  // Map the optional backend review metadata onto the card's props. Each is
  // undefined when the backend didn't supply it (or supplied null) → the card
  // hides that piece rather than fabricating it.
  const review = message.review;
  const confidenceLevel = review?.confidence?.level ?? undefined;
  const groundedCount = review?.grounding?.retrieved_count ?? undefined;
  const groundingSources = review?.grounding?.sources ?? undefined;

  return (
    <ReviewReplyCard
      body={message.body}
      status={reviewStatus(message, approve.isPending)}
      confidence={confidenceLevel}
      groundedCount={groundedCount}
      groundingSources={groundingSources}
      generationStatus={review?.generation_status}
      pending={pending}
      onApprove={() => approve.mutate(message.id, { onError: onError("approve") })}
      onReject={() => reject.mutate(message.id, { onError: onError("reject") })}
      onEdit={(nextBody) =>
        edit.mutate({ messageId: message.id, body: nextBody }, { onError: onError("save") })
      }
    />
  );
}
