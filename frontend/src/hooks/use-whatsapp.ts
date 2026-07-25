"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import type { ConnectWhatsAppPayload } from "@/lib/types";

const WHATSAPP_STATUS_KEY = "whatsapp-status" as const;
const WHATSAPP_WEBHOOK_CONFIG_KEY = "whatsapp-webhook-config" as const;

// `refetchInterval` is opt-in (undefined = no polling) so the always-mounted
// Settings page doesn't poll in the background — only the wizard's verify
// step (Sprint 71, Task B) passes one, while it's actually open and waiting
// for a real inbound message.
export function useWhatsAppStatus(options: { refetchInterval?: number } = {}) {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: [WHATSAPP_STATUS_KEY],
    queryFn: () => api.getWhatsAppStatus(getToken),
    enabled: isLoaded,
    refetchInterval: options.refetchInterval,
  });
}

export function useWhatsAppWebhookConfig() {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: [WHATSAPP_WEBHOOK_CONFIG_KEY],
    queryFn: () => api.getWhatsAppWebhookConfig(getToken),
    enabled: isLoaded,
    staleTime: Infinity, // static per deployment — never changes during a session
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
