"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { motion, MotionConfig } from "framer-motion";
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
const EASE_OUT = [0.16, 1, 0.3, 1] as const;

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
      {/* Key light — anchored behind the stage, not the section's midpoint,
          so the light reads as coming off the product. */}
      <div className="absolute right-0 top-0 h-[48rem] w-[48rem] -translate-y-1/4 translate-x-1/4 rounded-full bg-brand/[0.06] blur-3xl" />
      {/* Ambient tonal wash — neutral, ≤3% lightness per §4.3. */}
      <div className="absolute inset-0 bg-gradient-to-b from-foreground/[0.015] to-transparent" />
      {/* Left scrim — the reference's 5-stop readability gradient. Keeps the
          copy rail sitting on near-pure background regardless of the key
          light's spread. */}
      <div className="absolute inset-y-0 left-0 w-2/3 bg-gradient-to-r from-background via-background/85 to-transparent" />
      {/* Bottom fade — hands off to the next section without a hard edge. */}
      <div className="absolute inset-x-0 bottom-0 h-44 bg-gradient-to-t from-background to-transparent" />
    </div>
  );
}

export function Hero() {
  const reducedMotion = useReducedMotion();
  const [scenarioId, setScenarioId] = useState<ScenarioId>(DEFAULT_SCENARIO_ID);

  return (
    <MotionConfig reducedMotion={reducedMotion ? "always" : "never"}>
      <section className="relative overflow-hidden px-4 py-20 sm:px-6 sm:py-24 lg:flex lg:min-h-[94vh] lg:items-center lg:px-8 lg:py-12">
        <HeroAtmosphere />

        <div className="relative mx-auto w-full max-w-[1420px] lg:grid lg:grid-cols-[460px_1fr] lg:items-center lg:gap-9">
          <motion.div
            variants={staggerContainer}
            initial="hidden"
            animate="show"
            className="flex flex-col gap-6 text-center lg:text-left"
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
              className="text-[clamp(2.75rem,4.8vw,4.25rem)] font-extrabold leading-[1.08] tracking-[-0.04em]"
            >
              Never miss
              <br className="hidden lg:inline" />{" "}
              another
              <br className="hidden lg:inline" />{" "}
              <span className="text-brand">customer</span> message.
            </motion.h1>

            <motion.p
              variants={fadeUp}
              className="mx-auto max-w-[440px] text-pretty text-[1.0625rem] leading-[1.68] text-muted-foreground lg:mx-0"
            >
              HIRA answers your customers on WhatsApp, books appointments, follows
              up on leads, and hands the conversation to your team the moment it
              needs a human touch.
            </motion.p>

            {/* One undivided action, as in the reference — the old secondary
                "See how it works" link is gone, and the anchor it pointed at
                is still reachable from the header nav. */}
            <motion.div variants={fadeUp} className="flex justify-center lg:justify-start">
              <motion.div
                whileHover={{ y: -2, scale: 1.01 }}
                whileTap={{ y: 0, scale: 0.99 }}
                transition={{ type: "spring", stiffness: 300, damping: 24 }}
                className="inline-block"
              >
                <Button asChild size="xl" className="rounded-full px-[30px] shadow-e2">
                  <Link href="/sign-up">
                    Get started
                    <ArrowRight aria-hidden="true" />
                  </Link>
                </Button>
              </motion.div>
            </motion.div>

            <motion.div variants={fadeUp} className="mt-2">
              <HeroTrustPills />
            </motion.div>

            {/* The selector sits with the copy, not over the stage — it
                labels what the stage is playing, and at this position it is
                reachable before the demo in both reading and tab order. */}
            <motion.div variants={fadeUp} className="mt-1">
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
            transition={{ ...springIn, delay: 0.2, ease: EASE_OUT }}
            className="mt-16 lg:mt-0"
          >
            <OrchestrationStage key={scenarioId} scenarioId={scenarioId} />
          </motion.div>
        </div>
      </section>
    </MotionConfig>
  );
}
