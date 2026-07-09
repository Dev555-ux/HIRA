"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import type { CreateAppointmentPayload, RescheduleAppointmentPayload } from "@/lib/types";

const APPOINTMENTS_KEY = "appointments" as const;

export function useAppointments(params: { from?: string; to?: string } = {}) {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: [APPOINTMENTS_KEY, params],
    queryFn: () => api.listAppointments(getToken, params),
    enabled: isLoaded,
  });
}

export function useCreateAppointment() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateAppointmentPayload) => api.createAppointment(getToken, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: [APPOINTMENTS_KEY] }),
  });
}

export function useRescheduleAppointment() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: RescheduleAppointmentPayload }) =>
      api.rescheduleAppointment(getToken, id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: [APPOINTMENTS_KEY] }),
  });
}

export function useCancelAppointment() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.cancelAppointment(getToken, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [APPOINTMENTS_KEY] }),
  });
}
