import type { Transition, Variants } from "motion/react";

// Mirrors --motion-* / --ease-* in app/globals.css. Change both together.
export const duration = { ultraFast: 0.075, fast: 0.12, normal: 0.18, slow: 0.32, signature: 0.7 } as const;
export const ease = { out: [0.16, 1, 0.3, 1], in: [0.5, 0, 0.75, 0], inOut: [0.65, 0, 0.35, 1] } as const;

export const transition = {
  enter: { duration: duration.normal, ease: ease.out }, // 180ms — deterministic end time
  exit: { duration: duration.fast, ease: ease.in }, // 120ms
  reveal: { duration: duration.slow, ease: ease.out }, // 320ms
  settle: { type: "spring", stiffness: 170, damping: 26 }, // pointer-driven only, no overshoot
} satisfies Record<string, Transition>;

export const STAGGER = 0.04; // 40ms, DESIGN-MOTION-001 §5.3
export const STAGGER_CAP = 6; // items beyond the 6th share the 6th delay
export const staggerDelay = (i = 0) => Math.min(i, STAGGER_CAP) * STAGGER;

export const viewportOnce = { once: true, margin: "0px 0px -10% 0px", amount: 0.15 } as const;

// Scroll reveals: viewport-triggered section content, arriving as the reader
// scrolls to it. 320ms — the extra time reads as "arriving", not "late".
export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: (i = 0) => ({ opacity: 1, y: 0, transition: { ...transition.reveal, delay: staggerDelay(i) } }),
};

// Page entrances: the hero and above-the-fold content choreographed on first
// render. Same states, travel and stagger as fadeUp; transition.enter instead
// of transition.reveal, so a four-item entrance completes in
// 3 x 40ms + 180ms = 300ms (DESIGN-MOTION-001 §7.1).
export const fadeUpEnter: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: (i = 0) => ({ opacity: 1, y: 0, transition: { ...transition.enter, delay: staggerDelay(i) } }),
};
