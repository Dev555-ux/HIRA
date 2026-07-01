"use client";

import { useAuth, useUser } from "@clerk/nextjs";
import { useCallback } from "react";
import { AuthContext } from "@/lib/auth-context";

// Bridges Clerk's hooks into our AuthContext. Only mounted when Clerk is
// configured, so Clerk hooks are never called in mock mode.
export function ClerkBridge({ children }: { children: React.ReactNode }) {
  const { getToken, isLoaded } = useAuth();
  const { user } = useUser();

  const getTokenFn = useCallback(() => getToken(), [getToken]);

  return (
    <AuthContext.Provider
      value={{
        getToken: getTokenFn,
        isLoaded,
        mocked: false,
        user: user
          ? {
              name: user.fullName ?? user.username ?? "User",
              email: user.primaryEmailAddress?.emailAddress ?? "",
              imageUrl: user.imageUrl ?? null,
            }
          : null,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
