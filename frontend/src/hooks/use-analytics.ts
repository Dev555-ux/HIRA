"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import type { AnalyticsRange } from "@/lib/types";

// Analytics Phase 1 — one business-scoped request per range change (the
// backend's whole design point; see app/services/analytics.py). No
// refetchInterval — same "checking in on demand" reasoning as
// useFounderOverview, not a live operational monitor.
export function useAnalyticsDashboard(range: AnalyticsRange) {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: ["analytics-dashboard", range],
    queryFn: () => api.getAnalyticsDashboard(getToken, range),
    enabled: isLoaded,
  });
}
