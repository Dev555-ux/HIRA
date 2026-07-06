"use client";

import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";

export function useSendPlaygroundMessage() {
  const { getToken } = useAuthContext();
  return useMutation({
    mutationFn: (message: string) => api.sendPlaygroundMessage(getToken, message),
  });
}
