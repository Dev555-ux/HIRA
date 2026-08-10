import { ArrowRight, CheckCheck } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

// Leads with the customer's problem, not with what HIRA is — a first-time
// visitor should recognize the pain in the first sentence, then get the
// answer in the second. See product-proof.tsx immediately below for the
// "show, don't just tell" half of this same idea.
//
// V4: left-aligned from lg up, deliberately not centered like every other
// section — the hero is the one place the page argues rather than narrates,
// so it gets its own register. Centered on mobile/tablet, where an
// asymmetric hero has no room to breathe and just looks unbalanced. No
// decorative glow/blur behind the type: a soft radial gradient is the
// single most common "AI-generated landing page" default (frontend-design's
// own calibration list) — the actual bold move here is disciplined
// negative space, not atmosphere. The eyebrow drops its pill/border
// entirely (a bordered badge is the generic-SaaS default); a bare dot +
// tracked caption reads calmer and more considered.
//
// Post-launch self-critique: container tightened from max-w-5xl to max-w-4xl
// — at the wider size the empty right column on a large screen read as
// unfinished rather than composed. Still asymmetric, just not cavernous.
// The secondary link also dropped its own arrow icon — sitting next to the
// primary button's arrow, a second identical icon read as redundant
// clutter rather than a matched pair.
export function Hero() {
  return (
    <section className="mx-auto max-w-4xl px-4 py-16 text-center sm:px-6 sm:py-24 lg:py-32 lg:text-left">
      <div className="flex items-center justify-center gap-2.5 lg:justify-start">
        <span className="size-1.5 rounded-full bg-brand" aria-hidden="true" />
        <span className="text-[0.6875rem] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Founder Beta — limited early access
        </span>
      </div>

      {/* HIRA V2 refinement: the flat lg:text-8xl (96px) that shipped first
          measured fine on a tall/external monitor but pushed the CTA row
          near or past the fold on a common ~1440x900 laptop window (real
          height budget is closer to ~760px once browser chrome is out of
          it). Split the top tier in two instead of shrinking uniformly:
          xl (1280-1535, where a 1440-wide laptop actually lands) gets a
          dialed-back-but-still-larger-than-the-old-design size; 2xl
          (1536+, spacious external displays) keeps the full 96px. Laptops
          get a hero that fits; big monitors still get the drama. V4: capped
          at lg:max-w-2xl so the left-aligned headline keeps its own measure
          instead of stretching the full width of the wider lg:text-left
          section — the empty space to its right is the composition, not a
          layout accident. */}
      <h1 className="mt-7 text-balance text-6xl font-black tracking-tighter sm:text-7xl lg:max-w-2xl xl:text-[5.25rem] 2xl:text-8xl">
        Never miss another{" "}
        <mark
          className="rounded-lg bg-brand/15 px-1.5 py-0.5 text-brand [-webkit-box-decoration-break:clone] [box-decoration-break:clone]"
        >
          customer message
        </mark>
        .
      </h1>
      <p className="mt-6 max-w-md text-pretty text-lg text-muted-foreground sm:text-xl lg:mx-0 lg:max-w-sm">
        HIRA answers your customers on WhatsApp, books appointments, follows
        up on leads, and hands the conversation to your team the moment it
        needs a human touch.
      </p>
      <div className="mt-10 flex flex-col items-center gap-5 lg:items-start">
        <Button asChild size="xl">
          <Link href="/sign-up">
            Get started
            <ArrowRight aria-hidden="true" />
          </Link>
        </Button>
        <a
          href="#how-it-works"
          className="text-sm font-medium text-foreground underline-offset-4 hover:underline"
        >
          See how it works
        </a>
      </div>
      <p className="mt-8 flex items-center justify-center gap-2 text-sm text-muted-foreground lg:justify-start">
        <CheckCheck className="size-4 shrink-0 text-success" aria-hidden="true" />
        Starts in Assisted Mode — you approve every reply until you trust it
      </p>
    </section>
  );
}
