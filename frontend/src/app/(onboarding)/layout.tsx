"use client";

import { Bot } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { useOnboardingStatus } from "@/hooks/use-onboarding";

export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { data, isPending } = useOnboardingStatus();

  // A business that's already provisioned has no reason to see the
  // onboarding form again — send it straight to the dashboard.
  useEffect(() => {
    if (data?.has_business) {
      router.replace("/dashboard");
    }
  }, [data, router]);

  // isPending, not isLoading — see (dashboard)/layout.tsx's identical fix
  // for why: this query starts disabled until Clerk finishes loading, and
  // isLoading is false while disabled even with no data yet, which let this
  // gate briefly fall through to the real onboarding form for an
  // already-signed-in user before their status had actually loaded.
  if (isPending || data?.has_business) {
    return (
      <div className="flex min-h-screen items-center justify-center p-8">
        <Skeleton className="h-8 w-48" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-muted/30 p-4 sm:p-8">
      <div className="mb-8 flex items-center gap-2">
        <div className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Bot className="size-4" />
        </div>
        <span className="text-base font-semibold tracking-tight">HIRA</span>
      </div>
      <div className="w-full max-w-lg">{children}</div>
    </div>
  );
}
