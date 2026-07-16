"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { ErrorBoundary } from "@/components/error-boundary";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useOnboardingStatus } from "@/hooks/use-onboarding";
import { ApiError } from "@/lib/api";

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

function CenteredMessage({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="max-w-sm text-sm text-muted-foreground">{description}</p>
      {action}
    </div>
  );
}

// FTUE-1: a brand-new Clerk sign-up has no Business/User row until the
// onboarding form (POST /api/v1/onboarding/business) has actually succeeded
// — this layout is the one place that gate is enforced, so every page under
// it can safely assume get_current_principal will succeed. Previously, any
// *error* from the status check (as opposed to a clean "no business yet"
// result) fell through to rendering the dashboard anyway — a genuinely
// unprovisioned account could reach pages like Playground/Analytics/Business
// Knowledge, whose own calls then 401 ("Unknown user"), surfacing as opaque
// network errors. Every branch below now renders something explicit; none
// of them fall through to <AppShell> except the one confirmed-provisioned case.
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { data, isLoading, isError, error, refetch, isFetching } = useOnboardingStatus();

  useEffect(() => {
    if (data && !data.has_business) {
      router.replace("/onboarding");
    }
  }, [data, router]);

  if (isLoading) {
    return <FullPageLoading />;
  }

  if (isError) {
    // A 401 here means the Clerk session itself is invalid/expired — this
    // check never 401s just because a business doesn't exist yet (it
    // returns 200 with has_business: false for that case) — so this is a
    // real authentication failure, not a provisioning gap, and must not be
    // offered "Continue Setup" as if it were one.
    if (error instanceof ApiError && error.status === 401) {
      return (
        <CenteredMessage
          title="Your session has expired"
          description="Please sign in again to continue."
          action={
            <Button asChild>
              <Link href="/sign-in">Sign in</Link>
            </Button>
          }
        />
      );
    }
    return (
      <CenteredMessage
        title="Couldn't verify your account"
        description="Something went wrong while checking your account setup. Please try again."
        action={
          <Button onClick={() => refetch()} disabled={isFetching}>
            {isFetching ? "Retrying…" : "Retry"}
          </Button>
        }
      />
    );
  }

  if (!data?.has_business) {
    // Confirmed (not assumed) not yet provisioned. The effect above is
    // already navigating to /onboarding — this is the explicit state shown
    // for the moment that takes, and a safety net if navigation is ever
    // delayed, rather than a silent pass-through to real dashboard content.
    return (
      <CenteredMessage
        title="Welcome to HIRA"
        description="Let's finish setting up your AI employee."
        action={
          <Button asChild>
            <Link href="/onboarding">Continue Setup</Link>
          </Button>
        }
      />
    );
  }

  return (
    <AppShell>
      <ErrorBoundary>{children}</ErrorBoundary>
    </AppShell>
  );
}
