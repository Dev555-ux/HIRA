"use client";

import { domAnimation, LazyMotion, MotionConfig } from "motion/react";
import { transition } from "@/lib/motion";

// LazyMotion + `m` loads ~4.6kB of features for the initial render instead of
// the full ~34kB `motion` component. `strict` makes a stray `motion.*` inside
// this tree throw rather than silently pulling that bundle back in.
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
    <LazyMotion features={domAnimation} strict>
      <MotionConfig reducedMotion="user" transition={transition.enter}>
        {children}
      </MotionConfig>
    </LazyMotion>
  );
}
