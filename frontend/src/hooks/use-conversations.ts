"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import { POLL_INTERVAL_MS } from "@/lib/config";
import type { ConversationStatusFilter } from "@/lib/types";

const CONVERSATIONS_KEY = "conversations" as const;

export function useConversations(params: {
  search?: string;
  status?: ConversationStatusFilter;
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
