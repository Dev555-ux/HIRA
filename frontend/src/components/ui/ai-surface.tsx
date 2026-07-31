import * as React from "react";
import { cn } from "@/lib/utils";

// AI + review surfaces (DESIGN-MOTION-001 §4.4, §6.9). Generic building blocks
// for future screens — deliberately NOT wired into any page yet.

// Anything authored/handled by the AI sits on a distinct material: a faint left
// spine + near-threshold tint, so "your employee handled this" reads without a
// loud brand colour. Exported class so non-div consumers can match it exactly.
export const aiSurfaceClassName =
  "rounded-lg border border-l-2 border-border border-l-ai-spine bg-ai text-ai-foreground shadow-e1";

function AISurface({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn(aiSurfaceClassName, className)} {...props} />;
}

// The calm "awaiting you" surface for the review gate — where a draft comes to
// rest and waits for the founder (§6.9). Neutral, unhurried, never alarming.
export const reviewSurfaceClassName =
  "rounded-lg border bg-review text-review-foreground shadow-e1";

function ReviewSurface({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn(reviewSurfaceClassName, className)} {...props} />;
}

export { AISurface, ReviewSurface };
