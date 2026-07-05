"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { ErrorBoundary } from "@/components/error-boundary";
import { Skeleton } from "@/components/ui/skeleton";
import { useOnboardingStatus } from "@/hooks/use-onboarding";

function FullPageLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center p-8">
      <div className="w-full max-w-sm space-y-3">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
      </div>
    </div>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { data, isLoading, isError } = useOnboardingStatus();

  useEffect(() => {
    if (data && !data.has_business) {
      router.replace("/onboarding");
    }
  }, [data, router]);

  // Keep the dashboard chrome off-screen until we know a business exists —
  // otherwise a first-time user briefly sees the empty dashboard shell before
  // bouncing to /onboarding. On error, fail open to the dashboard rather than
  // trapping the user on a blank loading screen forever.
  if (isLoading || (data && !data.has_business && !isError)) {
    return <FullPageLoading />;
  }

  return (
    <AppShell>
      <ErrorBoundary>{children}</ErrorBoundary>
    </AppShell>
  );
}
