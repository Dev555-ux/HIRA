"use client";

import {
  AnimatePresence,
  domAnimation,
  LazyMotion,
  m,
  useReducedMotion,
  type HTMLMotionProps,
} from "motion/react";
import type { ReactNode } from "react";
import { fadeIn, fadeInUp, springs, staggerContainer, staggerItem } from "@/lib/motion";

// Mounted once in Providers. `strict` means every animated element in the
// tree must use `m.*`, never the full `motion.*` object — that's what keeps
// this at ~15kb gz instead of ~34kb (LazyMotion only loads the domAnimation
// feature set once, shared by every m.* usage, rather than each import
// pulling in its own copy of the animation engine).
export function MotionProvider({ children }: { children: ReactNode }) {
  return (
    <LazyMotion features={domAnimation} strict>
      {children}
    </LazyMotion>
  );
}

// `variants` is fixed per wrapper, not caller-configurable — omitted from
// the prop type rather than destructured-and-discarded so passing one is a
// type error, not a silent no-op.
type PresetMotionProps = Omit<HTMLMotionProps<"div">, "variants">;

export function FadeIn(props: PresetMotionProps) {
  const reduceMotion = useReducedMotion();
  return <m.div initial="hidden" animate="visible" variants={reduceMotion ? undefined : fadeIn} {...props} />;
}

export function FadeInUp(props: PresetMotionProps) {
  const reduceMotion = useReducedMotion();
  return (
    <m.div initial="hidden" animate="visible" variants={reduceMotion ? undefined : fadeInUp} {...props} />
  );
}

// Wrap a list's parent in <Stagger>, each row in <StaggerItem> — children
// animate in sequence instead of all at once. Reduces to a plain mount
// (no motion) under prefers-reduced-motion, same guarantee the CSS
// keyframes give elsewhere in this app.
export function Stagger(props: PresetMotionProps) {
  const reduceMotion = useReducedMotion();
  return (
    <m.div initial="hidden" animate="visible" variants={reduceMotion ? undefined : staggerContainer} {...props} />
  );
}

export function StaggerItem(props: PresetMotionProps) {
  const reduceMotion = useReducedMotion();
  return <m.div variants={reduceMotion ? undefined : staggerItem} {...props} />;
}

// Spring-based hover/tap feedback for anything that needs to compose with a
// later layout animation (plain hoverable cards should use
// `interactiveCardClassName` from ui/card.tsx instead — pure CSS, no JS,
// cheaper when spring physics aren't actually needed).
export function HoverLift(props: HTMLMotionProps<"div">) {
  const reduceMotion = useReducedMotion();
  return (
    <m.div
      whileHover={reduceMotion ? undefined : { y: -2 }}
      whileTap={reduceMotion ? undefined : { scale: 0.98 }}
      transition={springs.snappy}
      {...props}
    />
  );
}

export { AnimatePresence };
