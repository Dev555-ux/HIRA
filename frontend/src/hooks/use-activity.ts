"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";

// AI Activity (Sprint 84 — Dashboard Foundation): a narrative read over
// execution_traces, same "checking in on demand" reasoning as
// useAnalyticsDashboard — no refetchInterval, refreshed via Home's own
// manual refreshAll() alongside every other widget.
export function useAiActivity(limit = 6) {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: ["ai-activity", limit],
    queryFn: () => api.listActivity(getToken, limit),
    enabled: isLoaded,
  });
}
