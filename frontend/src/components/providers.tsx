"use client";

import { ClerkProvider } from "@clerk/nextjs";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useState } from "react";
import { ClerkBridge } from "@/components/auth/clerk-bridge";
import { ToastProvider } from "@/components/ui/toast";
import { AuthContext } from "@/lib/auth-context";
import { authEnabled, isProduction } from "@/lib/config";

const MOCK_USER = {
  name: "Dev User",
  email: "dev@hira.local",
  imageUrl: null,
};

function MockAuthProvider({ children }: { children: React.ReactNode }) {
  return (
    <AuthContext.Provider
      value={{
        getToken: async () => "dev-mock-token",
        user: MOCK_USER,
        isLoaded: true,
        mocked: true,
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
