import * as React from "react";
import { cn } from "@/lib/utils";

// A small state dot for an AI employee / system (DESIGN-MOTION-001 §6.2). Idle is
// perfectly still (stability reads as competence, not absence); only "working"
// carries a gentle pulse, which the global reduced-motion guard collapses.
export type ActivityState = "idle" | "working" | "waiting" | "success" | "error";

const dotColor: Record<ActivityState, string> = {
  idle: "bg-muted-foreground",
  working: "bg-foreground",
  waiting: "bg-warning",
  success: "bg-success",
  error: "bg-destructive",
};

interface ActivityDotProps extends React.HTMLAttributes<HTMLSpanElement> {
  state?: ActivityState;
  /** Accessible label; falls back to the state name. */
  label?: string;
}

function ActivityDot({ state = "idle", label, className, ...props }: ActivityDotProps) {
  return (
    <span
      role="status"
      aria-label={label ?? state}
      className={cn(
        "inline-block size-2 shrink-0 rounded-full",
        dotColor[state],
        state === "working" && "animate-pulse",
        className,
      )}
      {...props}
    />
  );
}

export { ActivityDot };
