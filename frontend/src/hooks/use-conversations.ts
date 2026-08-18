"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import { POLL_INTERVAL_MS } from "@/lib/config";
import type { ConversationChannelFilter, ConversationStatusFilter } from "@/lib/types";

const CONVERSATIONS_KEY = "conversations" as const;

export function useConversations(params: {
  search?: string;
  status?: ConversationStatusFilter;
  channel?: ConversationChannelFilter;
  limit?: number;
  offset?: number;
}) {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: [CONVERSATIONS_KEY, params],
    queryFn: () => api.listConversations(getToken, params),
    enabled: isLoaded,
    refetchInterval: POLL_INTERVAL_MS,
  });
}

export function useConversation(id: string | null) {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: [CONVERSATIONS_KEY, id],
    queryFn: () => api.getConversation(getToken, id as string),
    enabled: isLoaded && id !== null,
  });
}

export function useConversationMessages(id: string | null) {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: [CONVERSATIONS_KEY, id, "messages"],
    queryFn: () => api.listMessages(getToken, id as string),
    enabled: isLoaded && id !== null,
    refetchInterval: POLL_INTERVAL_MS,
  });
}

// Approve / edit / reject a pending AI reply from inside a conversation. Reuses
// the existing message endpoints (api.*). Unlike use-pending.ts (which is scoped
// to the flat /pending list cache), these invalidate the whole CONVERSATIONS_KEY
// tree, so the thread AND the conversation list both reflect the change from one
// place — no per-surface cache logic duplicated. Integration layer only; the
// ReviewReplyCard stays presentation-only.
export function usePendingReplyActions() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: [CONVERSATIONS_KEY] });

  const approve = useMutation({
    mutationFn: (messageId: string) => api.approveMessage(getToken, messageId),
    onSettled: invalidate,
  });
  const reject = useMutation({
    mutationFn: (messageId: string) => api.rejectMessage(getToken, messageId),
    onSettled: invalidate,
  });
  const edit = useMutation({
    mutationFn: ({ messageId, body }: { messageId: string; body: string }) =>
      api.updateDraft(getToken, messageId, body),
    onSettled: invalidate,
  });

  return { approve, reject, edit };
}
