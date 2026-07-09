"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import type { CreateLeadPayload, LeadStage, UpdateLeadPayload } from "@/lib/types";

const LEADS_KEY = "leads" as const;
const CUSTOMERS_KEY = "customers" as const;

export function useLeads(params: {
  search?: string;
  stage?: LeadStage;
  limit?: number;
  offset?: number;
} = {}) {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: [LEADS_KEY, params],
    queryFn: () => api.listLeads(getToken, params),
    enabled: isLoaded,
  });
}

export function useLead(id: string | null) {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: [LEADS_KEY, id],
    queryFn: () => api.getLead(getToken, id as string),
    enabled: isLoaded && id !== null,
  });
}

// Lead mutations touch both the /leads views and the Customers list/detail
// (which embeds the lead's stage), so both query namespaces are invalidated.
function useInvalidateLeadsAndCustomers() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: [LEADS_KEY] });
    qc.invalidateQueries({ queryKey: [CUSTOMERS_KEY] });
  };
}

export function useCreateLead() {
  const { getToken } = useAuthContext();
  const invalidate = useInvalidateLeadsAndCustomers();
  return useMutation({
    mutationFn: (payload: CreateLeadPayload) => api.createLead(getToken, payload),
    onSuccess: invalidate,
  });
}

export function useUpdateLead() {
  const { getToken } = useAuthContext();
  const invalidate = useInvalidateLeadsAndCustomers();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateLeadPayload }) =>
      api.updateLead(getToken, id, payload),
    onSuccess: invalidate,
  });
}

export function useDeleteLead() {
  const { getToken } = useAuthContext();
  const invalidate = useInvalidateLeadsAndCustomers();
  return useMutation({
    mutationFn: (id: string) => api.deleteLead(getToken, id),
    onSuccess: invalidate,
  });
}
