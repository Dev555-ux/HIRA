import { cn } from "@/lib/utils";

// Sprint 68 — Design System Consolidation. Every section heading on the
// marketing page (Problem, Solution, Features, How It Works, FAQ, Final CTA)
// previously re-declared the identical "text-3xl font-semibold
// tracking-tight" H2 by hand, and the optional supporting paragraph had
// drifted to three different sizes across sections with the same role
// (Sprint 67 audit, Typography #2). This is the one shared implementation.
// Width/measure is deliberately left to the caller via `className` — Problem/
// Features/How It Works want a narrower heading-only measure than the grid
// below it, Solution/FinalCta want the same width as their whole section,
// and FAQ wants none at all — none of that varies by accident, so it isn't
// collapsed into this component.
export function SectionHeader({
  title,
  description,
  className,
}: {
  title: string;
  description?: string;
  className?: string;
}) {
  return (
    <div className={cn("text-center", className)}>
      {/* Phase 2 — two optical corrections, applied here once so every
          section inherits them rather than each drifting on its own.
          tracking: type-display-lg sets --tracking-tight (-0.02em), which is
          a body-copy value. At 44px the hero's headline runs -0.045em, and a
          section heading sitting two tiers below it should be tightened in
          the same direction or the page reads as two typographers.
          measure + leading: the description was text-lg with default leading
          and no measure of its own, so it ran the full width of whatever
          container it was handed — up to ~1150px in Journey. Matched to the
          hero's body copy (17px / 1.6) and capped at 60ch. */}
      <h2 className="type-display-lg text-balance tracking-[-0.035em]">{title}</h2>
      {description ? (
        <p className="mx-auto mt-4 max-w-[60ch] text-pretty text-[1.0625rem] leading-[1.6] text-muted-foreground">
          {description}
        </p>
      ) : null}
    </div>
  );
}
