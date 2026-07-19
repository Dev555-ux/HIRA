import { ArrowRight, CheckCheck, Sparkle } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

// Leads with the customer's problem, not with what HIRA is — a first-time
// visitor should recognize the pain in the first sentence, then get the
// answer in the second. See product-proof.tsx immediately below for the
// "show, don't just tell" half of this same idea.
export function Hero() {
  return (
    <section className="mx-auto max-w-3xl px-4 py-16 text-center sm:px-6 sm:py-24">
      <Badge variant="outline" className="gap-1.5 text-muted-foreground">
        <Sparkle className="size-3" aria-hidden="true" />
        Founder Beta — limited early access
      </Badge>

      <h1 className="mt-6 text-4xl font-semibold tracking-tight sm:text-5xl">
        Never miss another customer message.
      </h1>
      <p className="mt-6 text-lg text-muted-foreground sm:text-xl">
        HIRA answers your customers on WhatsApp, books appointments, follows
        up on leads, and hands the conversation to your team the moment it
        needs a human touch.
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
    </section>
  );
}
