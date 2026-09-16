"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { motion, MotionConfig } from "motion/react";
import { useState } from "react";
import { HeroTrustPills } from "@/components/marketing/hero-trust-strip";
import {
  DEFAULT_SCENARIO_ID,
  OrchestrationStage,
  ScenarioSelector,
  type ScenarioId,
} from "@/components/marketing/signature-demo";
import { Button } from "@/components/ui/button";
import { useReducedMotion } from "@/hooks/use-reduced-motion";
import { ease } from "@/lib/motion";

// Cinematic rebuild — this hero is now the whole opening screen rather than
// the first of three stacked sections. What changed, and why:
//
//   1. Geometry. A fixed 460px copy rail beside a fluid stage (was a 5/7
//      split of a 12-col grid inside max-w-7xl), in a 1420px container with
//      a 36px gutter. The copy column lands at almost exactly the width it
//      had before — the entire difference goes to the stage, which now also
//      fills its track instead of being capped at max-w-lg.
//   2. Content. The trust signals and the scenario selector moved *into*
//      the copy rail, and the orchestration demo moved into the right
//      stage. The standalone HeroTrustStrip and SignatureDemo sections are
//      gone from the page as a result.
//   3. The old ProductDemo. Deleted, not relocated. It was a second,
//      separate chat state machine telling a different story (an AC service
//      call) from the orchestration engine's (a cleaning booking). A single
//      stage can only tell one, and the orchestration engine is the one
//      that drives the graph and the four scenarios. See the delivery notes
//      for the tests this removed.
const springIn = { type: "spring", stiffness: 130, damping: 20, mass: 0.7 } as const;

const staggerContainer = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1, delayChildren: 0.06 } },
};

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: springIn },
};

// The reference hero's depth comes from a 390 KB photographic backdrop plus
// two scrim layers and a 40s infinite drift. This reproduces the *lighting*
// — a warm key light off the upper right, falling off to clean background
// behind the copy — with four gradient layers and zero bytes of raster. It
// is deliberately static: DESIGN-MOTION-001 §6.8/§7.2 rule out ambient
// drift, and a moving backdrop behind live type is the first thing that
// makes a landing page feel cheap. aria-hidden + pointer-events-none, so
// it is inert to both assistive tech and the pointer.
function HeroAtmosphere() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      {/* Refinement pass — two blurred discs became one shaped light.
          `blur-3xl` on a solid circle can only ever produce a gaussian
          falloff, and every bloom built that way looks like every other
          one; the source reads as "a glow was added here" rather than as
          something illuminating the scene. hero-key-light is a multi-stop
          radial centred on the phone instead, so the curve is authored and
          the origin is the product. See globals.css for the stops. */}
      <div className="hero-key-light absolute inset-0" />
      {/* A vignette, not a wash: corners drop so the lit centre has something
          to be brighter *than*. Black rather than --foreground: foreground
          inverts with the theme, so in the dark scope it would have *lit*
          the corners — the exact opposite of a vignette. Black darkens in
          both, and is the only colour here that does not need a token. */}
      <div className="absolute inset-0 bg-[radial-gradient(120%_100%_at_50%_40%,transparent_45%,rgb(0_0_0_/_0.05)_100%)]" />
      {/* Left scrim — keeps the copy rail on near-pure background whatever
          the key light does. Narrower and softer than before: the light is
          now shaped rather than sprayed, so less needs masking, and at 7/12
          with a hard via-stop it was cutting a faint vertical seam down the
          middle of the hero. */}
      <div className="absolute inset-y-0 left-0 w-1/2 bg-gradient-to-r from-background from-15% via-background/60 to-transparent" />
      {/* Dither, last and over everything — see globals.css. Must sit above
          the gradients it is correcting, and below nothing else, since it
          covers the full section. */}
      <div className="hero-grain absolute inset-0" />
    </div>
  );
}

export function Hero() {
  const reducedMotion = useReducedMotion();
  const [scenarioId, setScenarioId] = useState<ScenarioId>(DEFAULT_SCENARIO_ID);

  return (
    <MotionConfig reducedMotion={reducedMotion ? "always" : "never"}>
      {/* `dark` scoped here, not toggled globally. HIRA's dark variant is
          `&:is(.dark *)` and its palette is a set of custom properties
          redeclared under `.dark` — so putting the class on this wrapper
          redeclares them here, and every descendant inherits the dark values
          with no component below needing to know. The trust pills, the
          scenario chips, the glass material and the whole orchestration
          stage flip on their own tokens; nothing is hardcoded, nothing else
          on the page is touched, and the dashboard is entirely unaffected.

          The dark scope is this wrapper rather than the section itself, so
          that the lighting rig spans the hero AND the strip that hands off
          to the light page. With the atmosphere confined to the section, its
          warm lower edge stopped dead at the section boundary and the
          neutral strip below started a visible tone step — the seam
          reappearing one element lower. One rig over both means the glow
          continues into the dissolve.

          `isolate` is required, not cosmetic: HeroAtmosphere is a -z-10
          child, and a negative-z child paints behind its parent's own
          background unless the parent is a stacking context. This wrapper
          has an opaque background, so without isolation the entire rig
          renders underneath it and is invisible. */}
      <div className="dark relative isolate overflow-hidden bg-background text-foreground">
        <HeroAtmosphere />

        <section className="relative px-4 py-20 sm:px-6 sm:py-24 lg:flex lg:min-h-[94vh] lg:items-center lg:px-8 lg:py-12">
        {/* Refinement pass — 460px/gap-9 → 440px/gap-5. Every pixel off the
            copy rail is a pixel the product gets. 420 was one step too far:
            it wrapped the scenario selector onto a second line, which cost
            more vertical than the 20px of width was worth. 440 is the
            narrowest the rail goes with the selector still on one row. */}
        <div className="relative mx-auto w-full max-w-[1420px] lg:grid lg:grid-cols-[440px_1fr] lg:items-center lg:gap-5">
          <motion.div
            variants={staggerContainer}
            initial="hidden"
            animate="show"
            // Liquid Glass PR-1 — gap-6 → gap-5, and the ad-hoc mt-2/mt-1
            // on the last two blocks are gone. At 1440×900 the stack ran
            // ~60px past the fold, cutting off the trust pills entirely:
            // the page's proof of who it's for was invisible on the most
            // common laptop viewport. One rhythm for the whole rail, no
            // per-block exceptions.
            className="flex flex-col gap-5 text-center lg:text-left"
          >
            <motion.div
              variants={fadeUp}
              className="flex items-center justify-center gap-2.5 lg:justify-start"
            >
              <span className="size-[7px] shrink-0 rounded-full bg-brand" aria-hidden="true" />
              <span className="text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground">
                Founder Beta — limited early access
              </span>
            </motion.div>

            {/* The reference headline is a tight three-line block, not
                balanced prose: line-height 1.08 and two hard breaks make it
                read as one carved object. The breaks are lg-only — on
                phones the same copy wraps naturally to whatever the width
                allows, which is why text-balance is gone rather than
                replaced. The accent is the single word "customer", plain
                brand colour with no background: the old <mark> chip existed
                to carry a resolved-state signal from a demo that no longer
                lives in this column. */}
            <motion.h1
              variants={fadeUp}
              // leading 1.08 → 1.02. At four lines of 68px type that is
              // ~24px of the ~60px overflow above, recovered without
              // touching the size — and it is the tighter setting the
              // reference uses, where the block reads as one carved object
              // rather than four stacked lines.
              //
              // Refinement pass — two optical corrections:
              //   tracking -0.04 → -0.045em. At display size the default
              //   fitting is loose; the reference's headline is noticeably
              //   tighter than its body, which is what makes it read as one
              //   mass rather than a row of words.
              //   -ml-[0.055em] at lg. Every glyph carries left side
              //   bearing, so a headline flush to a container sits a few
              //   px right of everything beneath it. Nudging by the bearing
              //   puts the "N" stem — the edge the eye actually reads — on
              //   the same line as the eyebrow dot and the body copy.
              //   Only at lg: below that the text is centred, where side
              //   bearing is symmetric and self-cancelling.
              className="text-[clamp(2.75rem,4.8vw,4.25rem)] font-extrabold leading-[1.02] tracking-[-0.045em] lg:-ml-[0.055em]"
            >
              Never miss
              <br className="hidden lg:inline" />{" "}
              another
              <br className="hidden lg:inline" />{" "}
              <span className="text-brand">customer</span> message
              {/* The reference accents the terminal period, not just the
                  noun — the sentence lands on a beat of brand colour
                  instead of trailing off in foreground ink. Purely
                  decorative colour on an existing character: the text
                  content, and what a screen reader announces, is
                  unchanged. */}
              <span className="text-brand">.</span>
            </motion.h1>

            <motion.p
              variants={fadeUp}
              // 1.68 → 1.6: still a comfortable measure for 17px at this
              // width, and paired with the tighter headline above it keeps
              // the copy rail reading as one composed block rather than
              // two differently-spaced ones. max-w follows the rail down to
              // 420 so the paragraph's right edge and the headline's share
              // one margin instead of ending 20px apart.
              className="mx-auto max-w-[420px] text-pretty text-[1.0625rem] leading-[1.6] tracking-[-0.005em] text-muted-foreground lg:mx-0"
            >
              HIRA answers your customers on WhatsApp, books appointments, follows
              up on leads, and hands the conversation to your team the moment it
              needs a human touch.
            </motion.p>

            {/* One undivided action, as in the reference — the old secondary
                "See how it works" link is gone, and the anchor it pointed at
                is still reachable from the header nav. */}
            {/* mt-1 on the row, not a gap change: the CTA is the one block
                in the rail that should sit slightly apart from the text it
                concludes. */}
            <motion.div variants={fadeUp} className="mt-1 flex justify-center lg:justify-start">
              <motion.div
                whileHover={{ y: -2, scale: 1.01 }}
                whileTap={{ y: 0, scale: 0.99 }}
                transition={{ type: "spring", stiffness: 300, damping: 24 }}
                // Release QA — framer-motion adds tabIndex={0} to any element
                // carrying whileTap, so it can receive a keyboard "tap". That
                // put a focusable <div> with no role and no accessible name
                // into the tab order directly before the real CTA: a keyboard
                // user tabbed onto nothing, then tabbed again to reach "Get
                // started". The link inside is the control; this wrapper is
                // only a motion container, so it is taken back out of the tab
                // order. Pre-existing, found by walking the real tab order.
                tabIndex={-1}
                className="relative inline-block"
              >
                {/* The reference haloes its CTA. It can, because it is a
                    white pill on black. Inverting that literally here would
                    mean glowing a near-black pill on near-white, which just
                    reads as a smudge — so the halo is warm, sits *under*
                    the button, and is the same brand hue as the key light
                    across the stage: the one lit object in the copy rail,
                    lit by the same source. Deliberately NOT glass: glass is
                    for surfaces that defer to what's behind them, and the
                    page's single primary action is the one thing that
                    should stay opaque and absolute. */}
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute -inset-3 -z-10 rounded-full bg-brand/20 blur-xl"
                />
                <Button asChild size="xl" className="rounded-full px-[30px] shadow-e3">
                  <Link href="/sign-up">
                    Get started
                    <ArrowRight aria-hidden="true" />
                  </Link>
                </Button>
              </motion.div>
            </motion.div>

            <motion.div variants={fadeUp}>
              <HeroTrustPills />
            </motion.div>

            {/* The selector sits with the copy, not over the stage — it
                labels what the stage is playing, and at this position it is
                reachable before the demo in both reading and tab order. */}
            <motion.div variants={fadeUp}>
              <p className="mb-2.5 text-[0.6875rem] font-bold uppercase tracking-[0.12em] text-muted-foreground">
                Try a scenario
              </p>
              <ScenarioSelector
                scenarioId={scenarioId}
                onChange={setScenarioId}
                className="lg:justify-start"
              />
            </motion.div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ ...springIn, delay: 0.2, ease: ease.out }}
            className="relative mt-16 lg:mt-0"
          >
            {/* The floor. Without it the stage is an object with nothing
                under it, which is most of why the scene reads as two
                columns side by side rather than one place. The pool sits
                behind the stage and is the same light as the key above —
                one source, its spill on the ground. */}
            {/* -inset-x-32, not inset-x-0: a radial wider than its own box
                gets clipped at the box's edges, which draws exactly the
                straight vertical line a soft light must never have. The
                element is given room for the gradient's full spread so the
                only edge on screen is the falloff's own. */}
            <div
              aria-hidden="true"
              className="hero-floor pointer-events-none absolute -inset-x-32 -bottom-6 -z-10 h-40"
            />
            <OrchestrationStage key={scenarioId} scenarioId={scenarioId} />
          </motion.div>
        </div>
        </section>

        {/* The handoff back to the light page, and the reason --surface-page
            exists. It is its own strip rather than a fade inside the hero: a
            320px ramp within the section necessarily runs underneath the
            trust pills and the scenario selector, and lightening the ground
            under dark-theme text leaves light-grey labels on a near-white
            wash — unreadable, and the first attempt did exactly that. A
            dedicated strip has no content over it, so the ramp is free to
            complete.
            `from-transparent`, not `from-background`: it sits inside the
            dark wrapper, so transparent means the hero's own lit ground —
            glow included — shows through and simply keeps going. Naming the
            background instead would repaint a flat neutral here and put the
            tone step back. --surface-page is declared on :root and never
            overridden, so `to-` still reaches the light page from inside the
            dark scope. 7rem reads as a dissolve rather than a rule, without
            becoming dead scroll. */}
        <div
          aria-hidden="true"
          className="h-28 bg-gradient-to-b from-transparent to-[var(--surface-page)]"
        />
      </div>
    </MotionConfig>
  );
}
