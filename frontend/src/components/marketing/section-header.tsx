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
      <h2 className="text-3xl font-semibold tracking-tight">{title}</h2>
      {description ? (
        <p className="mt-4 text-lg text-muted-foreground">{description}</p>
      ) : null}
    </div>
  );
}
