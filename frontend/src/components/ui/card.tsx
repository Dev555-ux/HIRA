import * as React from "react";
import { cn } from "@/lib/utils";

// Exported so non-div elements that can't use <Card> directly (e.g. an <li>
// inside a semantic <ol>, or a <details> that needs native disclosure
// behavior) can still match its exact visual spec via `cn(cardClassName, ...)`
// instead of re-declaring the class string by hand and drifting from it.
//
// HIRA V2: no hard border on the resting state — separation now comes from
// elevation (bumped e1→e2) and the card/background tone difference instead,
// a "floating surface" rather than a boxed one. A hairline border returns at
// border/60 only where a surface needs to read as adjacent to another
// same-toned surface at rest (see interactiveClassName below, which keeps its
// own border on hover/active for the same reason).
export const cardClassName = "rounded-2xl bg-card text-card-foreground shadow-e2";

// Opt-in hover lift for clickable cards (DESIGN-MOTION-001 §5.2: one step up
// on hover, back to resting on press). Off by default so static container
// cards are unchanged — only cards that are actually interactive should move.
// Resting is e2 (see cardClassName); hover steps to e3, press settles back.
const interactiveClassName =
  "transition-[box-shadow,transform] duration-[var(--motion-fast)] ease-[var(--ease-standard)] hover:-translate-y-px hover:shadow-e3 active:translate-y-0 active:shadow-e2";

// Sprint 87 — a small variant system so a page can express real visual
// hierarchy (a hero surface, a handful of primary panels, quieter secondary
// tiles, a barely-there grouping wrapper) without every screen hand-rolling
// its own one-off elevation/border/gradient combination. `primary` is
// exactly the pre-Sprint-87 `cardClassName` — every existing call site
// (defaulted, no `variant` prop) renders byte-identical to before.
export type CardVariant = "primary" | "secondary" | "minimal" | "hero";

const VARIANT_CLASS_NAME: Record<CardVariant, string> = {
  primary: cardClassName,
  // A quieter tier for compact, lower-priority tiles sitting alongside
  // primary panels (e.g. the three non-featured KPI tiles) — one shadow
  // step down, a touch of transparency so it visually recedes.
  secondary: "rounded-xl bg-card/70 text-card-foreground shadow-e1",
  // No fill, no shadow — a grouping wrapper for content that shouldn't read
  // as a "card" at all, just related items sharing a loose boundary.
  minimal: "rounded-xl bg-transparent text-card-foreground",
  // The page's one floating glass surface — a soft brand-tinted gradient
  // wash, a hairline brand border instead of the neutral default, and the
  // deepest resting elevation in the ladder. Reserved for the Dashboard
  // hero; never meant to be interactive (see VARIANT_INTERACTIVE below).
  hero: "rounded-3xl border border-brand/15 bg-gradient-to-br from-brand/[0.06] via-card to-card text-card-foreground shadow-e4",
};

const VARIANT_INTERACTIVE: Record<CardVariant, string> = {
  primary: interactiveClassName,
  secondary:
    "transition-[box-shadow,transform] duration-[var(--motion-fast)] ease-[var(--ease-standard)] hover:-translate-y-px hover:shadow-e2 active:translate-y-0 active:shadow-e1",
  minimal: "transition-colors duration-[var(--motion-fast)] ease-[var(--ease-standard)] hover:bg-accent/40",
  // A glass hero panel lifting on hover would read as clickable when it
  // isn't — `interactive` is a no-op on this variant rather than a trap.
  hero: "",
};

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  interactive?: boolean;
  variant?: CardVariant;
}

function Card({ className, interactive = false, variant = "primary", ...props }: CardProps) {
  return (
    <div
      className={cn(VARIANT_CLASS_NAME[variant], interactive && VARIANT_INTERACTIVE[variant], className)}
      {...props}
    />
  );
}

function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col space-y-1.5 p-6", className)} {...props} />;
}

function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("font-semibold leading-none tracking-tight", className)} {...props} />
  );
}

function CardDescription({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("text-sm text-muted-foreground", className)} {...props} />;
}

function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-6 pt-0", className)} {...props} />;
}

function CardFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex items-center p-6 pt-0", className)} {...props} />;
}

export { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter };
