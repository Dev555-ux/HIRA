"use client";

import { useAuth, useClerk, useUser } from "@clerk/nextjs";
import { useCallback } from "react";
import { AuthContext } from "@/lib/auth-context";

// Bridges Clerk's hooks into our AuthContext. Only mounted when Clerk is
// configured, so Clerk hooks are never called in mock mode.
export function ClerkBridge({ children }: { children: React.ReactNode }) {
  const { getToken, isLoaded } = useAuth();
  const { user } = useUser();
  const clerk = useClerk();

  const getTokenFn = useCallback(() => getToken(), [getToken]);
  const signOut = useCallback(() => clerk.signOut({ redirectUrl: "/" }), [clerk]);
  const openProfile = useCallback(() => clerk.openUserProfile(), [clerk]);

  return (
    <AuthContext.Provider
      value={{
        getToken: getTokenFn,
        isLoaded,
        mocked: false,
        signOut,
        openProfile,
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
