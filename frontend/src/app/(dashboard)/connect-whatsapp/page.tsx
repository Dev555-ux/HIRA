"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { CheckCircle2, Loader2, MessageCircle, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useEmbeddedSignup,
  type EmbeddedSignupFailure,
} from "@/hooks/use-embedded-signup";
import { useEmbeddedSignupConfig, useWhatsAppStatus } from "@/hooks/use-whatsapp";
import { embeddedSignupEnabled } from "@/lib/config";

const MANUAL_CONNECT_PATH = "/settings?whatsapp=connect";

/** Every failure, in the owner's language (DEC-052 §4).
 *
 * The language rule from DEC-052 §3 applies to all of it: no screen here
 * says webhook, callback URL, API, Graph API, access token, App Secret or
 * OAuth. `retry` marks the failures where trying again could plausibly work
 * — offering "try again" on a permanently-blocked number is worse than not
 * offering it, because it invites the owner to loop instead of acting. */
const FAILURES: Record<
  EmbeddedSignupFailure,
  { title: string; body: string; retry: boolean; manualFallback?: boolean }
> = {
  popup_closed: {
    title: "Looks like you didn't finish",
    body: "The Facebook window closed before your number was connected. No problem — nothing was changed, and you can pick up where you left off.",
    retry: true,
  },
  permission_denied: {
    title: "We're missing a permission",
    body: "Your AI receptionist needs permission to read and reply to messages on your number. Try again and approve each permission Facebook asks about.",
    retry: true,
  },
  state_invalid: {
    title: "This connection request expired",
    body: "Connection requests are only valid for a short while, for your security. Starting again takes a few seconds.",
    retry: true,
  },
  no_waba: {
    title: "We couldn't tell which business account to use",
    body: "Your Facebook account manages more than one WhatsApp business account, and we don't want to guess. Try again and pick the one your customers message.",
    retry: true,
  },
  no_phone_number: {
    title: "We couldn't tell which number to use",
    body: "That business account has more than one phone number, or none we can use yet. Try again and choose the number your customers already message.",
    retry: true,
  },
  phone_number_in_use: {
    title: "That number is already connected",
    body: "This WhatsApp number is connected to a different HIRA account. If that account is yours, disconnect it there first, then reconnect here.",
    retry: false,
  },
  pin_mismatch: {
    title: "That number has a PIN we can't match",
    body: "Your number has two-step verification set up with a PIN we don't hold. Turn two-step verification off for this number in WhatsApp Manager, then try again.",
    retry: false,
  },
  registration_failed: {
    title: "Your number couldn't be activated",
    body: "Facebook wouldn't activate this number for messaging. This usually means it still needs to be verified on Meta's side.",
    retry: true,
    manualFallback: true,
  },
  subscription_failed: {
    title: "Almost there — one step didn't finish",
    body: "Your number connected, but we couldn't finish switching messages over to your AI receptionist. Trying again picks up exactly where it stopped.",
    retry: true,
  },
  token_exchange_failed: {
    title: "Facebook didn't complete the connection",
    body: "Something went wrong between us and Facebook before your number was connected. Nothing was changed.",
    retry: true,
    manualFallback: true,
  },
  meta_unavailable: {
    title: "Facebook isn't responding right now",
    body: "This is on Facebook's side, not yours, and it's usually brief. Nothing was changed — try again in a moment.",
    retry: true,
  },
  sdk_unavailable: {
    title: "We couldn't open the Facebook window",
    body: "A browser extension or ad blocker usually causes this. Try pausing it for this page, or use a different browser.",
    retry: true,
    manualFallback: true,
  },
  network_error: {
    title: "We lost our connection",
    body: "We couldn't reach HIRA to finish setting things up. Check your internet connection and try again.",
    retry: true,
  },
};

function Shell({ children }: { children: React.ReactNode }) {
  return <div className="mx-auto max-w-lg">{children}</div>;
}

export default function ConnectWhatsAppPage() {
  const router = useRouter();
  const { data: config, isPending, isError } = useEmbeddedSignupConfig();
  const { data: status } = useWhatsAppStatus();
  const { phase, failure, displayPhoneNumber, start, reset } = useEmbeddedSignup();

  const backendReady = !isPending && !isError && config?.enabled === true;
  const alreadyConnected = status?.connected === true;

  useEffect(() => {
    if (!embeddedSignupEnabled) {
      router.replace(MANUAL_CONNECT_PATH);
    }
  }, [router]);

  if (!embeddedSignupEnabled) return null;

  if (isPending) {
    return (
      <Shell>
        <Skeleton className="h-40 w-full" />
      </Shell>
    );
  }

  if (!backendReady) {
    return (
      <Shell>
        <PageHeader title="Connect WhatsApp" />
        <Card>
          <CardHeader>
            <CardTitle>Connect your WhatsApp number</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              One-click setup isn&apos;t available on this deployment yet.{" "}
              <Link href={MANUAL_CONNECT_PATH} className="underline">
                Connect with your existing Meta credentials instead
              </Link>
              .
            </p>
          </CardContent>
        </Card>
      </Shell>
    );
  }

  if (phase === "success") {
    const number = displayPhoneNumber ?? status?.display_phone_number;
    return (
      <Shell>
        <PageHeader title="Connect WhatsApp" />
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="size-5 text-primary" aria-hidden="true" />
              <CardTitle>You&apos;re connected</CardTitle>
            </div>
            <CardDescription>
              {number
                ? `Messages to ${number} will now be answered by your AI receptionist.`
                : "Messages to your number will now be answered by your AI receptionist."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {/* The most convincing proof a non-technical owner can get is a
                real message arriving — more convincing than any status text
                (DEC-052 §7's differentiator). Just a wa.me deep link. */}
            {number && (
              <Button asChild className="w-full">
                <a
                  href={`https://wa.me/${number.replace(/[^\d]/g, "")}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  <MessageCircle className="size-4" aria-hidden="true" />
                  Send yourself a test message
                </a>
              </Button>
            )}
            <Button variant="secondary" className="w-full" asChild>
              <Link href="/">Go to dashboard</Link>
            </Button>
          </CardContent>
        </Card>
      </Shell>
    );
  }

  if (phase === "connecting" || phase === "opening" || phase === "awaiting_popup") {
    const label =
      phase === "connecting"
        ? "Setting up your AI receptionist…"
        : "Opening Facebook…";
    return (
      <Shell>
        <PageHeader title="Connect WhatsApp" />
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden="true" />
              <CardTitle>{label}</CardTitle>
            </div>
            <CardDescription>
              {phase === "connecting"
                ? "Confirming your number and activating messaging. This takes a few seconds — please keep this page open."
                : "Finish the steps in the Facebook window. We'll take over as soon as you're done."}
            </CardDescription>
          </CardHeader>
          {/* No action here on purpose: a founder shouldn't be able to
              double-submit mid-flow (DEC-052 §3.6). */}
          <CardContent aria-live="polite" className="text-sm text-muted-foreground">
            {phase === "connecting" ? "Almost there." : "Waiting for Facebook…"}
          </CardContent>
        </Card>
      </Shell>
    );
  }

  if (phase === "error" && failure) {
    const copy = FAILURES[failure];
    return (
      <Shell>
        <PageHeader title="Connect WhatsApp" />
        <Card>
          <CardHeader>
            <CardTitle>{copy.title}</CardTitle>
            <CardDescription>{copy.body}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {copy.retry && (
              <Button className="w-full" onClick={() => void start()}>
                <RefreshCw className="size-4" aria-hidden="true" />
                Try again
              </Button>
            )}
            {copy.manualFallback && (
              <p className="text-sm text-muted-foreground">
                Still stuck?{" "}
                <Link href={MANUAL_CONNECT_PATH} className="underline">
                  Connect with your existing Meta credentials instead
                </Link>
                .
              </p>
            )}
            <Button variant="ghost" className="w-full" onClick={reset}>
              Back
            </Button>
          </CardContent>
        </Card>
      </Shell>
    );
  }

  // Welcome (DEC-052 §3.1), or Reconnect for a business that already has a
  // connection — same flow, different framing, because telling someone
  // who's already connected to "connect" reads as a mistake.
  return (
    <Shell>
      <PageHeader title="Connect WhatsApp" />
      <Card>
        <CardHeader>
          <CardTitle>
            {alreadyConnected
              ? "Reconnect your WhatsApp number"
              : "Connect your existing WhatsApp Business account"}
          </CardTitle>
          <CardDescription>
            {alreadyConnected
              ? "Your setup, knowledge and conversation history all stay exactly as they are. Reconnecting just re-establishes the link with Facebook."
              : "You'll sign in with Facebook and confirm your business details — that's Meta's own verification, not something we can skip. It takes about two minutes."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!alreadyConnected && (
            <div className="rounded-md border p-3 text-sm text-muted-foreground">
              <p className="mb-1 font-medium text-foreground">You&apos;ll need</p>
              <ul className="list-inside list-disc space-y-1">
                <li>Access to the Facebook account for your business</li>
                <li>Your business phone number, to receive a confirmation code</li>
              </ul>
            </div>
          )}
          <Button className="w-full" onClick={() => void start()}>
            {alreadyConnected ? "Reconnect WhatsApp" : "Connect WhatsApp"}
          </Button>
          <p className="text-sm text-muted-foreground">
            Prefer to enter your own Meta credentials?{" "}
            <Link href={MANUAL_CONNECT_PATH} className="underline">
              Use manual setup
            </Link>
            .
          </p>
        </CardContent>
      </Card>
    </Shell>
  );
}
