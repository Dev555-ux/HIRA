"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import type { CreateCustomerPayload, UpdateCustomerPayload } from "@/lib/types";

const CUSTOMERS_KEY = "customers" as const;

export function useCustomers(params: { search?: string; limit?: number; offset?: number } = {}) {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: [CUSTOMERS_KEY, params],
    queryFn: () => api.listCustomers(getToken, params),
    enabled: isLoaded,
  });
}

export function useCustomer(id: string | null) {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: [CUSTOMERS_KEY, id],
    queryFn: () => api.getCustomer(getToken, id as string),
    enabled: isLoaded && id !== null,
  });
}

export function useCustomerTimeline(
  id: string | null,
  params: { limit?: number; offset?: number } = {},
) {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: [CUSTOMERS_KEY, id, "timeline", params],
    queryFn: () => api.getCustomerTimeline(getToken, id as string, params),
    enabled: isLoaded && id !== null,
  });
}

export function useCreateCustomer() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateCustomerPayload) => api.createCustomer(getToken, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: [CUSTOMERS_KEY] }),
  });
}

export function useUpdateCustomer() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateCustomerPayload }) =>
      api.updateCustomer(getToken, id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: [CUSTOMERS_KEY] }),
  });
}

export function useDeleteCustomer() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteCustomer(getToken, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [CUSTOMERS_KEY] }),
  });
}
