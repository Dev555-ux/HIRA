"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";

const PLAYGROUND_HISTORY_KEY = ["playground-history"] as const;

// Demo Chat's persisted transcript — reused verbatim across page loads
// instead of the local-only React state the original Playground UI kept,
// so a refresh no longer drops the conversation.
export function usePlaygroundHistory() {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: PLAYGROUND_HISTORY_KEY,
    queryFn: () => api.getPlaygroundHistory(getToken),
    enabled: isLoaded,
  });
}

export function useSendPlaygroundMessage() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (message: string) => api.sendPlaygroundMessage(getToken, message),
    onSuccess: () => qc.invalidateQueries({ queryKey: PLAYGROUND_HISTORY_KEY }),
  });
}
