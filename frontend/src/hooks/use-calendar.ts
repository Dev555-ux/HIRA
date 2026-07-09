"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import type { UpdateCalendarSettingsPayload } from "@/lib/types";

const CALENDAR_SETTINGS_KEY = "calendar-settings" as const;
const CALENDAR_STATUS_KEY = "calendar-status" as const;

export function useCalendarSettings() {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: [CALENDAR_SETTINGS_KEY],
    queryFn: () => api.getCalendarSettings(getToken),
    enabled: isLoaded,
  });
}

export function useUpdateCalendarSettings() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: UpdateCalendarSettingsPayload) =>
      api.updateCalendarSettings(getToken, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: [CALENDAR_SETTINGS_KEY] }),
  });
}

export function useCalendarStatus() {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: [CALENDAR_STATUS_KEY],
    queryFn: () => api.getCalendarStatus(getToken),
    enabled: isLoaded,
  });
}

export function useStartCalendarConnect() {
  const { getToken } = useAuthContext();
  return useMutation({
    mutationFn: () => api.startCalendarConnect(getToken),
  });
}

export function useDisconnectCalendar() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.disconnectCalendar(getToken),
    onSuccess: () => qc.invalidateQueries({ queryKey: [CALENDAR_STATUS_KEY] }),
  });
}

export function useAvailability(
  params: { starts_at: string; ends_at: string } | null,
) {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: ["calendar-availability", params],
    queryFn: () => api.getAvailability(getToken, params as { starts_at: string; ends_at: string }),
    enabled: isLoaded && params !== null,
  });
}
