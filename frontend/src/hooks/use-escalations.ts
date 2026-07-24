"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import { POLL_INTERVAL_MS } from "@/lib/config";
import type { EscalationAssignedFilter, EscalationStatusFilter } from "@/lib/types";

const ESCALATIONS_KEY = "escalations" as const;

export function useEscalations(params: {
  status?: EscalationStatusFilter;
  assigned?: EscalationAssignedFilter;
  limit?: number;
  offset?: number;
}) {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: [ESCALATIONS_KEY, params],
    queryFn: () => api.listEscalations(getToken, params),
    enabled: isLoaded,
    refetchInterval: POLL_INTERVAL_MS,
  });
}

export function useAssignEscalation() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.assignEscalation(getToken, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [ESCALATIONS_KEY] }),
  });
}

export function useUnassignEscalation() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.unassignEscalation(getToken, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [ESCALATIONS_KEY] }),
  });
}

export function useResolveEscalation() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.resolveEscalation(getToken, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [ESCALATIONS_KEY] }),
  });
}
