"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import type { ConnectWhatsAppPayload } from "@/lib/types";

const WHATSAPP_STATUS_KEY = "whatsapp-status" as const;

export function useWhatsAppStatus() {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: [WHATSAPP_STATUS_KEY],
    queryFn: () => api.getWhatsAppStatus(getToken),
    enabled: isLoaded,
  });
}

export function useConnectWhatsApp() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ConnectWhatsAppPayload) => api.connectWhatsApp(getToken, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: [WHATSAPP_STATUS_KEY] }),
  });
}

export function useDisconnectWhatsApp() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.disconnectWhatsApp(getToken),
    onSuccess: () => qc.invalidateQueries({ queryKey: [WHATSAPP_STATUS_KEY] }),
  });
}
