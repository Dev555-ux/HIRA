import * as React from "react";
import { cn } from "@/lib/utils";
import { ActivityDot, type ActivityState } from "./activity-dot";

// A compact status indicator: a state dot + a label (DESIGN-MOTION-001 §6.2
// state grammar). Distinct from Badge — Badge is a generic content label; this
// reads a live AI/system state at a glance and pairs a colour with a dot + text
// (never colour alone, per §13 accessibility). Composes ActivityDot.
interface StatusPillProps extends React.HTMLAttributes<HTMLSpanElement> {
  state?: ActivityState;
  children: React.ReactNode;
}

function StatusPill({ state = "idle", children, className, ...props }: StatusPillProps) {
  return (
    <span
      className={cn(
        "type-caption inline-flex items-center gap-1.5 rounded-full border bg-card px-2.5 py-0.5 text-card-foreground shadow-e1",
        className,
      )}
      {...props}
    >
      <ActivityDot state={state} />
      <span>{children}</span>
    </span>
  );
}

export { StatusPill };
