"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import type { BusinessSettings } from "@/lib/types";

const SETTINGS_KEY = ["settings"] as const;

export function useSettings() {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: SETTINGS_KEY,
    queryFn: () => api.getSettings(getToken),
    enabled: isLoaded,
  });
}

export function useUpdateSettings() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: BusinessSettings) => api.updateSettings(getToken, payload),
    onSuccess: (data) => qc.setQueryData<BusinessSettings>(SETTINGS_KEY, data),
  });
}
