"use client";

import { LazyMotion, MotionConfig } from "motion/react";
import { transition } from "@/lib/motion";

// LazyMotion + `m` loads the feature set separately from the ~34kB `motion`
// component. `strict` makes a stray `motion.*` inside this tree throw rather
// than silently pulling that bundle back in.
//
// T3.6(b) — the features now load through a dynamic import, so the projection
// code the chat thread needs for layout animation lands in its own chunk
// instead of the initial bundle. `.then(mod => mod.default)` is load-bearing:
// LazyFeatureBundle is `() => Promise<FeatureBundle>`, and handing it the
// module namespace does not compile (spec amendment A5).
//
// reducedMotion="user" replaces the previous hand-rolled
// `reducedMotion={hook ? "always" : "never"}`: the hook initialises to false on
// the client, so the first frame animated for people who had asked it not to.
// Motion reads the media query itself, and keeps opacity while dropping
// transforms — which is what DESIGN-MOTION-001 §3.7 specifies.
//
// Mounted around the marketing tree only. The dashboard uses no Motion, and
// should not pay for it.
export function MotionProvider({ children }: { children: React.ReactNode }) {
  return (
    <LazyMotion
      features={() => import("@/components/motion/features").then((mod) => mod.default)}
      strict
    >
      <MotionConfig reducedMotion="user" transition={transition.enter}>
        {children}
      </MotionConfig>
    </LazyMotion>
  );
}
