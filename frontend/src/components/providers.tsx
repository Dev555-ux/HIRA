"use client";

import { ClerkProvider } from "@clerk/nextjs";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useState } from "react";
import { ClerkBridge } from "@/components/auth/clerk-bridge";
import { ToastProvider, useToast } from "@/components/ui/toast";
import { AuthContext } from "@/lib/auth-context";
import { authEnabled, clerkKeyLooksLikeTestKey, isProduction } from "@/lib/config";

// Sprint 77 (RC-1 finding): a pk_test_ key silently serving production
// traffic has no user-visible symptom until Clerk's own request cap is hit
// — this makes it loud in the one place a founder would actually see it
// (server/build logs), at module load, not on every render.
if (isProduction && clerkKeyLooksLikeTestKey) {
  console.warn(
    "[HIRA] NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY is a pk_test_... (development) key in a " +
      "production build. Development Clerk instances have strict usage limits and are not " +
      "meant to serve real users — replace it with a pk_live_... key from a production " +
      "Clerk instance.",
  );
}

const MOCK_USER = {
  name: "Dev User",
  email: "dev@hira.local",
  imageUrl: null,
};

// Mock mode has no real session/account to act on — signOut/openProfile still
// give feedback rather than silently doing nothing, matching the "no dead
// clicks" standard the rest of the app follows.
function MockAuthProvider({ children }: { children: React.ReactNode }) {
  const { toast } = useToast();

  return (
    <AuthContext.Provider
      value={{
        getToken: async () => "dev-mock-token",
        user: MOCK_USER,
        isLoaded: true,
        mocked: true,
        signOut: () =>
          toast({
            title: "Mock auth",
            description: "There's no real session to sign out of in local/dev mode.",
          }),
        openProfile: () =>
          toast({
            title: "Mock auth",
            description: "Profile management isn't available in local/dev mode.",
          }),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

function AuthMisconfigured() {
  return (
    <div className="flex min-h-screen items-center justify-center p-6 text-center">
      <div className="max-w-md">
        <h1 className="text-lg font-semibold">Authentication not configured</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          This deployment is running in production without Clerk credentials.
          Set <code>NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY</code> to enable sign-in.
          Mock auth is never used in production.
        </p>
      </div>
    </div>
  );
}

function AuthLayer({ children }: { children: React.ReactNode }) {
  if (authEnabled) {
    return (
      <ClerkProvider>
        <ClerkBridge>{children}</ClerkBridge>
      </ClerkProvider>
    );
  }
  // No Clerk key. Allowed only outside production.
  if (isProduction) {
    return <AuthMisconfigured />;
  }
  return <MockAuthProvider>{children}</MockAuthProvider>;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 15_000, retry: 1, refetchOnWindowFocus: false },
        },
      }),
  );

  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <AuthLayer>{children}</AuthLayer>
        </ToastProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
