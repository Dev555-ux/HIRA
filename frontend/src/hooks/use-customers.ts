"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";

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
