"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import type { CreateBusinessPayload } from "@/lib/types";

const ONBOARDING_STATUS_KEY = ["onboarding-status"] as const;

export function useOnboardingStatus() {
  const { getToken, isLoaded } = useAuthContext();
  return useQuery({
    queryKey: ONBOARDING_STATUS_KEY,
    queryFn: () => api.getOnboardingStatus(getToken),
    enabled: isLoaded,
  });
}

export function useCreateBusiness() {
  const { getToken } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateBusinessPayload) => api.createBusiness(getToken, payload),
    onSuccess: (business) => {
      qc.setQueryData(ONBOARDING_STATUS_KEY, { has_business: true, business });
    },
  });
}
