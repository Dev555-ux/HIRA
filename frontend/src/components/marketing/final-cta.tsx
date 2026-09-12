"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import type { CSSProperties } from "react";
import { Button } from "@/components/ui/button";
import { WorkingIndicator } from "@/components/ui/working-indicator";
import { Reveal } from "@/components/marketing/reveal";

// V4 "Signal & Quiet": the page's second Signal band, bookending Solution's
// dark statement earlier — same bg-primary/text-primary-foreground tokens,
// same reason (the close deserves the page's other register, not another
// quiet section). Bypasses SectionHeader for the same bespoke-statement
// reason Solution does. WorkingIndicator is the one shared component reused
// as-is here, but its two color classes (bg-border/bg-foreground) are tuned
// for the light ambient page — on this dark island they'd be nearly
// invisible, so the wrapping div locally overrides those two CSS variables
// to primary-foreground rather than forking the component or hand-copying
// its class string.
//
// Post-launch self-critique: this band originally matched Solution's
// treatment closely enough to read as the same idea copy-pasted rather
// than two distinct moments. Deliberately unequal now: smaller headline,
// font-bold instead of font-black (a reprise, not a rematch), no "eyebrow"
// label — Solution earns the loudest typographic moment on the page,
// this one earns the only brand-filled button instead.
const workingIndicatorDarkOverride = {
  "--color-border": "var(--primary-foreground)",
  "--color-foreground": "var(--primary-foreground)",
} as CSSProperties;

// Sprint 66 PR-8 — one static backdrop, exactly as the brief asks: a
// blurred brand-colored glow centered on the section's own bottom edge, so
// only its upper half shows inside the band — a horizon glow rising from
// below the fold, not a centered spotlight. aria-hidden, pointer-events-
// none, zero keyframes; its own overflow-hidden clips the oversized blur
// to the section bounds, so it can't cause horizontal scroll. Echoes the
// CTA button's own bg-brand rather than introducing a new color. Opacity
// stays low enough that bg-primary/text-primary-foreground contrast at the
// text itself is unaffected — the glow sits low in the band, not behind
// the headline.
//
// Sprint 66 PR-10 — dark-mode fix, verified empirically (computed style +
// pixel-sampled the rendered screenshot, not just eyeballed):
// two distinct bugs, not one.
//
// 1. The real bug, in both themes: this <section> is `position: relative`
//    with no z-index, which per spec does NOT create a stacking context —
//    so this glow's negative z-index escaped to a further-out ancestor's
//    stacking context instead of staying scoped locally, and got painted
//    behind other content (confirmed: getComputedStyle reported the
//    correct color the whole time, but the rendered pixels showed zero
//    trace of it even at 50% opacity, or a fully solid test red). One
//    `isolate` on the section gives it its own stacking context, which is
//    the standard fix for exactly this — and the light-mode glow (bg-
//    brand/30) reads *stronger* now too, since it was being partly hidden
//    by the same bug the whole time, not just dimmed by low opacity.
//
// 2. dark-mode-specific: bg-primary flips to near-white in dark mode (the
//    same inversion solution.tsx documents), so a light brand glow reads
//    as invisible against an already-light band regardless of the bug
//    above. dark:bg-primary-foreground/20 swaps in the band's own
//    (now-dark) foreground token instead — a soft shadow pooling at the
//    horizon rather than a light glow, correct for a bright band the same
//    way the brand glow is correct for a dark one. Same element, same
//    size/position/blur — only the color source changes per theme.
function FinalCtaAtmosphere() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      <div className="absolute left-1/2 top-full h-[24rem] w-[48rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-brand/30 blur-3xl dark:bg-primary-foreground/20" />
    </div>
  );
}

export function FinalCta() {
  // DESIGN-MOTION-001 §7.8: hover does one working-line pass beneath the
  // final CTA — the last thing a visitor sees before converting is a
  // glimpse of the employee ready to start. No pulsing/breathing on its own.
  const [hovering, setHovering] = useState(false);

  return (
    <section className="relative isolate bg-primary py-24 text-primary-foreground sm:py-32 lg:py-40">
      <FinalCtaAtmosphere />
      <Reveal className="relative mx-auto max-w-2xl px-4 text-center sm:px-6">
        <h2 className="text-balance text-3xl font-bold tracking-tight sm:text-4xl">
          Never miss another message again
        </h2>
        <p className="mx-auto mt-5 max-w-lg text-pretty text-lg leading-relaxed text-primary-foreground/70">
          Set up your knowledge base, connect WhatsApp, and test HIRA
          yourself — before a single customer sees a reply.
        </p>
        <div className="mt-12 flex flex-col items-center gap-4">
          <Button
            asChild
            size="xl"
            className="bg-brand text-brand-foreground hover:bg-brand/90"
            onMouseEnter={() => setHovering(true)}
            onMouseLeave={() => setHovering(false)}
            onFocus={() => setHovering(true)}
            onBlur={() => setHovering(false)}
          >
            <Link href="/sign-up">
              Get started
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
          <div style={workingIndicatorDarkOverride} className="w-24">
            <WorkingIndicator state={hovering ? "working" : "idle"} label="Ready to start" />
          </div>
        </div>
      </Reveal>
    </section>
  );
}
