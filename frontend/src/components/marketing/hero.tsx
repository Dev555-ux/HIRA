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
    <section className="mx-auto max-w-3xl px-4 py-14 text-center sm:px-6 sm:py-20">
      <Badge variant="outline" className="gap-1.5 text-muted-foreground">
        <Sparkle className="size-3" aria-hidden="true" />
        Founder Beta — limited early access
      </Badge>

      {/* HIRA V2 refinement: the flat lg:text-8xl (96px) that shipped first
          measured fine on a tall/external monitor but pushed the CTA row
          near or past the fold on a common ~1440x900 laptop window (real
          height budget is closer to ~760px once browser chrome is out of
          it). Split the top tier in two instead of shrinking uniformly:
          xl (1280-1535, where a 1440-wide laptop actually lands) gets a
          dialed-back-but-still-larger-than-the-old-design size; 2xl
          (1536+, spacious external displays) keeps the full 96px. Laptops
          get a hero that fits; big monitors still get the drama. */}
      <h1 className="mt-5 text-balance text-6xl font-black tracking-tighter sm:text-7xl xl:text-[5.25rem] 2xl:text-8xl">
        Never miss another{" "}
        <mark
          className="rounded-md bg-brand/15 px-1 text-brand [-webkit-box-decoration-break:clone] [box-decoration-break:clone]"
        >
          customer message
        </mark>
        .
      </h1>
      <p className="mt-5 text-pretty text-lg text-muted-foreground sm:text-xl">
        HIRA answers your customers on WhatsApp, books appointments, follows
        up on leads, and hands the conversation to your team the moment it
        needs a human touch.
      </p>
      <div className="mt-7 flex flex-col items-center justify-center gap-3 sm:flex-row">
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
      <p className="mt-5 flex items-center justify-center gap-2 text-sm text-muted-foreground">
        <CheckCheck className="size-4 shrink-0 text-success" aria-hidden="true" />
        Starts in Assisted Mode — you approve every reply until you trust it
      </p>
    </section>
  );
}
