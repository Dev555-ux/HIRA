import type { Transition, Variants } from "motion/react";

// Shared Motion tokens — keyed to the 3-tier scale already documented in
// globals.css (micro ~150-200ms / signature ~700ms / ambient ~1.5-2s) so
// nothing here invents a fourth timing outside that scale. Every animated
// component should pull from here rather than hand-writing its own
// duration/spring, same discipline the CSS keyframes already follow.

export const springs = {
  // Default UI spring for hover/tap/small layout moves — snappy, minimal
  // overshoot. Springs are velocity-driven, not duration-driven, but this
  // settles in roughly the micro-interaction tier's timeframe.
  snappy: { type: "spring", stiffness: 500, damping: 35, mass: 1 } satisfies Transition,
  // Softer spring for larger FLIP layout animations (sidebar collapse, a
  // sliding tab indicator) — a stiffer spring reads as jittery over a
  // bigger travel distance.
  layout: { type: "spring", stiffness: 380, damping: 32 } satisfies Transition,
} as const;

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.2, ease: "easeOut" } },
};

export const fadeInUp: Variants = {
  hidden: { opacity: 0, y: 4 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.2, ease: "easeOut" } },
};

// Parent orchestrates timing; children should carry `staggerItem` (an alias
// of fadeInUp) so each one still animates itself, just offset in sequence.
export const staggerContainer: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.05 } },
};

export const staggerItem: Variants = fadeInUp;
