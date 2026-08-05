import * as React from "react";
import { cn } from "@/lib/utils";

// AI + review surfaces (DESIGN-MOTION-001 §4.4, §6.9). Generic building blocks
// for future screens — deliberately NOT wired into any page yet.

// Anything authored/handled by the AI sits on a distinct material: a
// near-threshold tint plus a left spine in the brand color — the one place
// Cobalt marks authorship rather than interactivity (IMPLEMENTATION-
// ROADMAP-001 M4; DESIGN-SCREENBOOK-002 §1's "Cobalt Thread"). This is a
// deliberate split from WorkingIndicator's body-language line, which stays
// neutral by design (see that file) — the spine says "this is AI-authored,"
// the line says "this is what the AI is doing right now," and only one of
// those two ever needed the brand color. Exported class so non-div
// consumers can match it exactly.
export const aiSurfaceClassName =
  "rounded-lg border border-l-2 border-border border-l-brand bg-ai text-ai-foreground shadow-e1";

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
