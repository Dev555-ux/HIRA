import { ArrowRight, CheckCheck } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export function Hero() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-24">
      <div className="mx-auto max-w-3xl text-center">
        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
          An AI receptionist that answers WhatsApp before your customer gives up
        </h1>
        <p className="mt-6 text-lg text-muted-foreground sm:text-xl">
          HIRA replies to customer messages on WhatsApp using your own business
          knowledge, books appointments straight into your calendar, and hands
          off to you the moment it isn&apos;t sure — so no message sits unanswered.
        </p>
        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Button asChild size="lg">
            <Link href="/sign-up">
              Get started
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <a href="#how-it-works">See how it works</a>
          </Button>
        </div>
        <p className="mt-6 flex items-center justify-center gap-2 text-sm text-muted-foreground">
          <CheckCheck className="size-4 shrink-0 text-success" aria-hidden="true" />
          Starts in Assisted Mode — you approve every reply until you trust it
        </p>
      </div>
    </section>
  );
}
