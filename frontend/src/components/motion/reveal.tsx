"use client";

import * as m from "motion/react-m";
import { fadeUp, viewportOnce } from "@/lib/motion";

// The project's one entrance system. A section wraps its content in Reveal;
// an ordered list uses RevealGroup + RevealItem so the items can carry the
// staggered delay (applied in T3.4 — the group animates nothing itself).
//
// data-reveal marks "starts hidden, revealed by JS": the noscript rule in
// app/layout.tsx targets it so this content is visible without a script.
export function Reveal({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <m.div
      data-reveal
      className={className}
      variants={fadeUp}
      initial="hidden"
      whileInView="show"
      viewport={viewportOnce}
    >
      {children}
    </m.div>
  );
}

// Container animates nothing itself; items carry the staggered delay.
export function RevealGroup({
  as = "ul",
  className,
  children,
}: {
  as?: "ul" | "ol";
  className?: string;
  children: React.ReactNode;
}) {
  const Tag = as === "ol" ? m.ol : m.ul;
  return (
    <Tag className={className} initial="hidden" whileInView="show" viewport={viewportOnce}>
      {children}
    </Tag>
  );
}

export function RevealItem({
  i,
  className,
  children,
}: {
  i: number;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <m.li data-reveal className={className} variants={fadeUp} custom={i}>
      {children}
    </m.li>
  );
}
