import * as React from "react";
import { cn } from "@/lib/utils";
import { ActivityDot, type ActivityState } from "./activity-dot";

// The AI employee's identity mark. Deliberately a plain monogram, not a face,
// icon, or "magic AI" glyph (DESIGN-MOTION-001 §6.0 — no anthropomorphic
// clichés, no sparkle/orb iconography; HIRA's AI reads as competent staff,
// and competent staff don't sparkle). Brand-toned so it's recognizable at a
// glance as "the AI," distinct from a customer's plain-neutral avatar.
function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase();
}

const SIZE: Record<"sm" | "default" | "lg", string> = {
  sm: "size-6 text-[10px]",
  default: "size-8 text-xs",
  lg: "size-10 text-sm",
};

export interface AIAvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  /** The AI employee's name, e.g. "Maya". Used for initials and the accessible label. */
  name: string;
  size?: "sm" | "default" | "lg";
  /** When supplied, overlays an ActivityDot in the corner (§6.2 state grammar). */
  state?: ActivityState;
}

function AIAvatar({ name, size = "default", state, className, ...props }: AIAvatarProps) {
  return (
    <div className={cn("relative inline-flex shrink-0", className)} {...props}>
      <div
        role="img"
        aria-label={name}
        className={cn(
          "flex items-center justify-center rounded-md bg-brand/15 font-semibold text-brand",
          SIZE[size],
        )}
      >
        {initials(name)}
      </div>
      {state && (
        <ActivityDot
          state={state}
          label={`${name} is ${state}`}
          className="absolute -bottom-0.5 -right-0.5 ring-2 ring-background"
        />
      )}
    </div>
  );
}

export { AIAvatar };
