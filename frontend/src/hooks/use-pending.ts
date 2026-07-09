"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import { POLL_INTERVAL_MS } from "@/lib/config";
import type { PendingReply } from "@/lib/types";

const PENDING_KEY = ["pending"] as const;

export function usePending() {
  const { getToken } = useAuthContext();
  return useQuery({
    queryKey: PENDING_KEY,
    queryFn: () => api.listPending(getToken),
    refetchInterval: POLL_INTERVAL_MS,
  });
}

export function useApprove() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.approveMessage(getToken, id),
    onMutate: async (id: string) => {
      await qc.cancelQueries({ queryKey: PENDING_KEY });
      const prev = qc.getQueryData<PendingReply[]>(PENDING_KEY);
      qc.setQueryData<PendingReply[]>(
        PENDING_KEY,
        (old) => old?.filter((m) => m.id !== id) ?? [],
      );
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(PENDING_KEY, ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: PENDING_KEY }),
  });
}

export function useUpdateDraft() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: string }) =>
      api.updateDraft(getToken, id, body),
    onSuccess: (result) => {
      qc.setQueryData<PendingReply[]>(
        PENDING_KEY,
        (old) => old?.map((m) => (m.id === result.id ? { ...m, body: result.body } : m)) ?? [],
      );
    },
  });
}

export function useReject() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.rejectMessage(getToken, id),
    onMutate: async (id: string) => {
      await qc.cancelQueries({ queryKey: PENDING_KEY });
      const prev = qc.getQueryData<PendingReply[]>(PENDING_KEY);
      qc.setQueryData<PendingReply[]>(
        PENDING_KEY,
        (old) => old?.filter((m) => m.id !== id) ?? [],
      );
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(PENDING_KEY, ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: PENDING_KEY }),
  });
}

export function useRegenerate() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.regenerateMessage(getToken, id),
    onSuccess: (result) => {
      qc.setQueryData<PendingReply[]>(
        PENDING_KEY,
        (old) => old?.map((m) => (m.id === result.id ? { ...m, body: result.body } : m)) ?? [],
      );
    },
  });
}

export function useEscalate() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.escalateMessage(getToken, id),
    onMutate: async (id: string) => {
      await qc.cancelQueries({ queryKey: PENDING_KEY });
      const prev = qc.getQueryData<PendingReply[]>(PENDING_KEY);
      qc.setQueryData<PendingReply[]>(
        PENDING_KEY,
        (old) => old?.filter((m) => m.id !== id) ?? [],
      );
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(PENDING_KEY, ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: PENDING_KEY }),
  });
}
