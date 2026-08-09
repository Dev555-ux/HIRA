import * as React from "react";
import { cn } from "@/lib/utils";

// A determinate progress bar. Deliberately not the ambient/indeterminate
// texture — that's WorkingIndicator's job (DESIGN-MOTION-001 §5.10 draws the
// line between the two: this is for a real, measurable fraction — onboarding
// completion, upload/import progress — not "the AI is doing something".
export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  /** 0–100. */
  value: number;
  label?: string;
}

function Progress({ value, label, className, ...props }: ProgressProps) {
  const clamped = Math.min(100, Math.max(0, value));
  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(clamped)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-muted", className)}
      {...props}
    >
      <div
        className="h-full rounded-full bg-primary transition-[width] duration-[var(--motion-normal)] ease-[var(--ease-out-quart)]"
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

export { Progress };
