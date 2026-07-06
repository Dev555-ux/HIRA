"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import type {
  CreateKbEntryPayload,
  ImportWebsitePayload,
  KbEntry,
  UpdateKbEntryPayload,
} from "@/lib/types";

const KB_KEY = ["kb-entries"] as const;

export function useKbEntries() {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: KB_KEY,
    queryFn: () => api.listKbEntries(getToken),
    enabled: isLoaded,
  });
}

export function useCreateKbEntry() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateKbEntryPayload) => api.createKbEntry(getToken, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: KB_KEY }),
  });
}

export function useUpdateKbEntry() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateKbEntryPayload }) =>
      api.updateKbEntry(getToken, id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: KB_KEY }),
  });
}

export function useImportWebsite() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ImportWebsitePayload) => api.importWebsite(getToken, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: KB_KEY }),
  });
}

export function useDeleteKbEntry() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteKbEntry(getToken, id),
    onMutate: async (id: string) => {
      await qc.cancelQueries({ queryKey: KB_KEY });
      const prev = qc.getQueryData<KbEntry[]>(KB_KEY);
      qc.setQueryData<KbEntry[]>(KB_KEY, (old) => old?.filter((e) => e.id !== id) ?? []);
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(KB_KEY, ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: KB_KEY }),
  });
}
