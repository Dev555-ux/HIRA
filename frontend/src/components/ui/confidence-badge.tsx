import * as React from "react";
import { cn } from "@/lib/utils";

// Shows how confident the AI is about a draft/answer (DESIGN-MOTION-001 §6 —
// trust made legible). Level is paired with a label, never colour alone. Uses
// the neutral + status palette only; no new hues.
export type ConfidenceLevel = "high" | "medium" | "low";

const levelStyle: Record<ConfidenceLevel, string> = {
  high: "border-transparent bg-success/15 text-success",
  medium: "border-transparent bg-warning/15 text-warning",
  low: "border-transparent bg-muted text-muted-foreground",
};

const levelLabel: Record<ConfidenceLevel, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
};

interface ConfidenceBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  level: ConfidenceLevel;
  /** Override the default label text. */
  children?: React.ReactNode;
}

function ConfidenceBadge({ level, children, className, ...props }: ConfidenceBadgeProps) {
  return (
    <span
      aria-label={levelLabel[level]}
      className={cn(
        "type-caption inline-flex items-center rounded-full border px-2 py-0.5 font-medium",
        levelStyle[level],
        className,
      )}
      {...props}
    >
      {children ?? levelLabel[level]}
    </span>
  );
}

export { ConfidenceBadge };
