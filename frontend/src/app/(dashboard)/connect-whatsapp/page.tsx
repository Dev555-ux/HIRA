"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useEmbeddedSignupConfig, useStartEmbeddedSignup } from "@/hooks/use-whatsapp";
import { embeddedSignupEnabled } from "@/lib/config";

const MANUAL_CONNECT_PATH = "/settings?whatsapp=connect";

/** Track B entry screen (TODOS.md ONBOARD-E) — "Continue with Facebook",
 * gated behind ENABLE_EMBEDDED_SIGNUP on both frontend and backend. Does not
 * replace guided-manual v1's own wizard at MANUAL_CONNECT_PATH, which stays
 * the production path (ONBOARD-D) and is completely unaffected by anything
 * on this page.
 *
 * Two independent checks before rendering a live button, so a
 * misconfiguration never surfaces as a broken click: the frontend's own env
 * flag (fast, no network call — see lib/config.ts) and the backend's
 * /embedded-signup/config response (authoritative — the frontend flag could
 * drift from the backend's in a two-service deploy). Either one being off
 * routes straight to the manual flow. */
export default function ConnectWhatsAppPage() {
  const router = useRouter();
  const { data, isPending, isError } = useEmbeddedSignupConfig();
  const startEmbeddedSignup = useStartEmbeddedSignup();

  const backendReady = !isPending && !isError && data?.enabled === true;

  useEffect(() => {
    if (!embeddedSignupEnabled) {
      router.replace(MANUAL_CONNECT_PATH);
    }
  }, [router]);

  if (!embeddedSignupEnabled) {
    return null;
  }

  if (isPending) {
    return (
      <div className="mx-auto max-w-lg">
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg">
      <PageHeader title="Connect WhatsApp" />
      <Card>
        <CardHeader>
          <CardTitle>Connect your existing WhatsApp Business account</CardTitle>
          <CardDescription>
            Sign in with Facebook to link the WhatsApp number your customers already message.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {backendReady ? (
            <>
              <Button
                className="w-full"
                disabled={startEmbeddedSignup.isPending}
                onClick={() => startEmbeddedSignup.mutate()}
              >
                {startEmbeddedSignup.isPending ? "Connecting…" : "Continue with Facebook"}
              </Button>
              {startEmbeddedSignup.isError && (
                <p className="text-sm text-destructive">
                  Continue with Facebook isn&apos;t ready on this deployment yet. Use{" "}
                  <Link href={MANUAL_CONNECT_PATH} className="underline">
                    manual setup
                  </Link>{" "}
                  instead.
                </p>
              )}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              Continue with Facebook isn&apos;t available on this deployment yet.{" "}
              <Link href={MANUAL_CONNECT_PATH} className="underline">
                Connect with your existing Meta credentials instead
              </Link>
              .
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
