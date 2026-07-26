"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";

// No refetchInterval — this is a founder checking in on demand, not a live
// operational monitor with its own paging/alerting; manual refresh (React
// Query's own refetch()) is enough at this stage.
export function useFounderOverview() {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: ["founder-overview"],
    queryFn: () => api.getFounderOverview(getToken),
    enabled: isLoaded,
    retry: false, // a 404 (not-a-founder) should surface immediately, not retry
  });
}

// Sprint 76 — AI Employee Observability. Same "no polling" reasoning as
// useFounderOverview above.
export function useFounderAiMetrics() {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: ["founder-ai-metrics"],
    queryFn: () => api.getFounderAiMetrics(getToken),
    enabled: isLoaded,
    retry: false,
  });
}

export function useFounderTraces(params: { business_id?: string; limit?: number; offset?: number }) {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: ["founder-traces", params],
    queryFn: () => api.listFounderTraces(getToken, params),
    enabled: isLoaded,
    retry: false,
  });
}

export function useFounderTraceDetail(traceId: string | null) {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: ["founder-trace", traceId],
    queryFn: () => api.getFounderTraceDetail(getToken, traceId as string),
    enabled: isLoaded && traceId !== null,
    retry: false,
  });
}
