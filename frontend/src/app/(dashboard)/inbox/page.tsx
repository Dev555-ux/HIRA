"use client";

import {
  AlertTriangle,
  ArrowLeft,
  Inbox as InboxIcon,
  MessageSquare,
  RefreshCw,
  Search,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ChannelBadge } from "@/components/channel-badge";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { PendingReviewContainer } from "@/components/pending-review-container";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusPill } from "@/components/ui/status-pill";
import {
  useConversation,
  useConversationMessages,
  useConversations,
} from "@/hooks/use-conversations";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { CHANNELS } from "@/lib/channels";
import { CONVERSATION_STATUS_BADGE } from "@/lib/conversations";
import { VARIANT_TO_STATE } from "@/lib/status";
import type {
  Conversation,
  ConversationChannelFilter,
  ConversationStatusFilter,
  Message,
} from "@/lib/types";
import { cn, formatRelativeTime } from "@/lib/utils";

const FILTERS: { label: string; value: ConversationStatusFilter | undefined }[] = [
  { label: "All", value: undefined },
  { label: "Open", value: "open" },
  { label: "Pending", value: "pending" },
  { label: "Closed", value: "closed" },
];

// Its own axis, not merged into FILTERS above — status and channel filter
// independently (Sprint 65 PR 4). Built from CHANNELS so a future channel
// needs no change here.
const CHANNEL_FILTERS: { label: string; value: ConversationChannelFilter | undefined }[] = [
  { label: "All", value: undefined },
  ...Object.entries(CHANNELS).map(([value, { label }]) => ({
    label,
    value: value as ConversationChannelFilter,
  })),
];

const MESSAGE_STATUS_BADGE: Partial<
  Record<
    Message["status"],
    { label: string; variant: "warning" | "success" | "destructive" | "secondary" | "outline" }
  >
> = {
  pending_approval: { label: "Pending approval", variant: "warning" },
  sending: { label: "Sending…", variant: "secondary" },
  sent: { label: "Sent", variant: "success" },
  failed: { label: "Failed", variant: "destructive" },
  rejected: { label: "Rejected", variant: "outline" },
  // Matches CONVERSATION_STATUS_BADGE's "escalated" (lib/conversations.ts) —
  // Sprint 77: without this, the honest-fallback/escalation Messages that
  // Objective A/D now create (app/ai/processing.py) rendered as a plain
  // bubble with no visual signal anything went wrong.
  escalated: { label: "Escalated", variant: "warning" },
};

export default function InboxPage() {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<ConversationStatusFilter | undefined>(undefined);
  const [channelFilter, setChannelFilter] = useState<ConversationChannelFilter | undefined>(
    undefined,
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const debouncedQuery = useDebouncedValue(query);

  const { data, isPending, isError, error, isFetching, refetch } = useConversations({
    search: debouncedQuery || undefined,
    status: filter,
    channel: channelFilter,
  });
  const conversations = data?.data ?? [];

  return (
    <>
      <Suspense fallback={null}>
        <ConversationDeepLink onSelect={setSelectedId} />
      </Suspense>
      <PageHeader
        title="Inbox"
        description="Customer conversations from every connected channel."
        action={
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className={isFetching ? "animate-spin" : ""} />
            Refresh
          </Button>
        }
      />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            aria-label="Search conversations"
            placeholder="Search conversations…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <Button
              key={f.label}
              size="sm"
              variant={filter === f.value ? "secondary" : "ghost"}
              onClick={() => setFilter(f.value)}
            >
              {f.label}
            </Button>
          ))}
        </div>
        <div className="flex gap-1" role="group" aria-label="Filter by channel">
          {CHANNEL_FILTERS.map((f) => (
            <Button
              key={f.label}
              size="sm"
              variant={channelFilter === f.value ? "secondary" : "ghost"}
              onClick={() => setChannelFilter(f.value)}
            >
              {f.label}
            </Button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <ConversationList
          conversations={conversations}
          isPending={isPending}
          isError={isError}
          error={error}
          onRetry={refetch}
          selectedId={selectedId}
          onSelect={setSelectedId}
          hasQuery={query.length > 0 || filter !== undefined || channelFilter !== undefined}
        />
        <ConversationDetail conversationId={selectedId} onBack={() => setSelectedId(null)} />
      </div>
    </>
  );
}

// The Escalations workspace links here with ?conversation=<id> so "Open
// conversation" jumps straight to the message timeline instead of making the
// team member search for it — same ?whatsapp=connect/Suspense pattern
// Settings already uses for its own deep-link.
function ConversationDeepLink({ onSelect }: { onSelect: (id: string) => void }) {
  const searchParams = useSearchParams();
  useEffect(() => {
    const id = searchParams.get("conversation");
    if (id) onSelect(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);
  return null;
}

function ConversationList({
  conversations,
  isPending,
  isError,
  error,
  onRetry,
  selectedId,
  onSelect,
  hasQuery,
}: {
  conversations: Conversation[];
  isPending: boolean;
  isError: boolean;
  error: unknown;
  onRetry: () => void;
  selectedId: string | null;
  onSelect: (id: string) => void;
  hasQuery: boolean;
}) {
  return (
    <Card className={cn("min-h-[420px]", selectedId !== null ? "hidden lg:block" : "block")}>
      <CardContent className="p-0">
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
            title="Couldn't load conversations"
            description={error instanceof Error ? error.message : "Something went wrong."}
            action={
              <Button size="sm" onClick={onRetry}>
                Retry
              </Button>
            }
            className="border-0 py-16"
          />
        )}

        {!isPending && !isError && conversations.length === 0 && (
          <EmptyState
            icon={InboxIcon}
            title={hasQuery ? "No matches" : "No conversations yet"}
            description={
              hasQuery
                ? "Try a different search term or filter."
                : "Conversations will appear here once a customer messages a connected channel."
            }
            action={
              !hasQuery && (
                <Button asChild size="sm" variant="outline">
                  <Link href="/demo">Try Demo Chat</Link>
                </Button>
              )
            }
            className="border-0 py-16"
          />
        )}

        {!isPending && !isError && conversations.length > 0 && (
          <ul className="divide-y">
            {conversations.map((conv) => {
              const statusBadge = CONVERSATION_STATUS_BADGE[conv.status];
              const name = conv.customer.display_name || conv.customer.wa_phone;
              return (
                <li key={conv.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(conv.id)}
                    className={cn(
                      "flex w-full flex-col gap-1 px-4 py-3 text-left transition-colors hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                      selectedId === conv.id && "bg-accent",
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium">{name}</span>
                      {conv.last_message_at && (
                        <span className="shrink-0 text-xs text-muted-foreground">
                          {formatRelativeTime(conv.last_message_at)}
                        </span>
                      )}
                    </div>
                    <p className="truncate text-xs text-muted-foreground">
                      {conv.preview ?? "No messages yet"}
                    </p>
                    <div className="flex gap-1">
                      <ChannelBadge channel={conv.channel} />
                      <StatusPill state={VARIANT_TO_STATE[statusBadge.variant]}>
                        {statusBadge.label}
                      </StatusPill>
                      {conv.has_pending_approval && (
                        <StatusPill state="waiting">Pending</StatusPill>
                      )}
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function ConversationDetail({
  conversationId,
  onBack,
}: {
  conversationId: string | null;
  onBack: () => void;
}) {
  const { data: conversation, isPending: isPendingConversation } =
    useConversation(conversationId);
  const {
    data: messagesData,
    isPending: isPendingMessages,
    isError,
    error,
    refetch,
  } = useConversationMessages(conversationId);
  const messages = messagesData?.data ?? [];

  if (conversationId === null) {
    return (
      <Card className="hidden min-h-[420px] lg:flex">
        <CardContent className="flex h-full w-full items-center justify-center p-6">
          <div className="text-center text-sm text-muted-foreground">
            <Badge variant="secondary" className="mb-3">
              Message timeline
            </Badge>
            <p>Select a conversation to view its message timeline.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const name = conversation?.customer.display_name || conversation?.customer.wa_phone;

  return (
    <Card className="flex min-h-[420px] flex-col">
      <div className="flex items-center gap-3 border-b px-4 py-3">
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          aria-label="Back to conversations"
          onClick={onBack}
        >
          <ArrowLeft />
        </Button>
        {isPendingConversation ? (
          <Skeleton className="h-5 w-32" />
        ) : (
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <p className="truncate text-sm font-medium">{name}</p>
              {conversation && <ChannelBadge channel={conversation.channel} />}
            </div>
            {conversation && (
              <p className="text-xs text-muted-foreground">{conversation.customer.wa_phone}</p>
            )}
          </div>
        )}
      </div>

      <CardContent className="flex-1 space-y-3 overflow-y-auto p-4">
        {isPendingMessages && (
          <div className="space-y-3">
            <Skeleton className="h-10 w-2/3" />
            <Skeleton className="ml-auto h-10 w-2/3" />
            <Skeleton className="h-10 w-1/2" />
          </div>
        )}

        {isError && (
          <EmptyState
            icon={AlertTriangle}
            title="Couldn't load messages"
            description={error instanceof Error ? error.message : "Something went wrong."}
            action={
              <Button size="sm" onClick={() => refetch()}>
                Retry
              </Button>
            }
            className="border-0 py-10"
          />
        )}

        {!isPendingMessages && !isError && messages.length === 0 && (
          <EmptyState
            icon={MessageSquare}
            title="No messages yet"
            description="Messages in this conversation will appear here."
            className="border-0 py-10"
          />
        )}

        {!isPendingMessages &&
          !isError &&
          messages.map((message) =>
            // Only pending_approval AI replies get the review experience
            // (ReviewReplyCard); every other message type renders exactly as
            // before.
            message.direction === "outbound" && message.status === "pending_approval" ? (
              <PendingReviewContainer key={message.id} message={message} />
            ) : (
              <MessageBubble key={message.id} message={message} />
            ),
          )}
      </CardContent>
    </Card>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const statusBadge =
    message.direction === "outbound" ? MESSAGE_STATUS_BADGE[message.status] : undefined;

  return (
    <div
      className={cn(
        "flex flex-col gap-1",
        message.direction === "outbound" ? "items-end" : "items-start",
      )}
    >
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-2.5 text-sm",
          message.direction === "outbound"
            ? "rounded-tr-sm bg-secondary text-secondary-foreground"
            : "rounded-tl-sm bg-muted",
        )}
      >
        {message.body}
      </div>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>{formatRelativeTime(message.created_at)}</span>
        {statusBadge && <Badge variant={statusBadge.variant}>{statusBadge.label}</Badge>}
      </div>
    </div>
  );
}
