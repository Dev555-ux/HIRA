import * as React from "react";
import { cn } from "@/lib/utils";

// The "working line" (DESIGN-MOTION-001 §6.1) — HIRA's single AI body-language
// primitive. One thin, foreground-toned line that stays flat and still when
// idle and carries a travelling segment when work is flowing. Every AI state is
// a modulation of this one line, so the AI always reads as one entity, variously
// occupied — never a soundboard of unrelated effects, never a chat-app "typing
// dots" cliché. Generic; not wired to a screen yet.
export type WorkingState = "idle" | "thinking" | "working" | "waiting";

// idle: still. thinking: unhurried travel. working: the same travel (speed is a
// property of the shared motion tokens, not this component). waiting: paused,
// dimmed — blocked, patiently.
const isActive = (state: WorkingState) => state === "thinking" || state === "working";

interface WorkingIndicatorProps extends React.HTMLAttributes<HTMLDivElement> {
  state?: WorkingState;
  /** Accessible status text announced to screen readers (e.g. "Thinking…"). */
  label?: string;
}

function WorkingIndicator({
  state = "idle",
  label,
  className,
  ...props
}: WorkingIndicatorProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={label ?? state}
      className={cn(
        "relative h-px w-full overflow-hidden bg-border",
        state === "waiting" && "opacity-50",
        className,
      )}
      {...props}
    >
      {isActive(state) && (
        <span
          aria-hidden
          className="absolute inset-y-0 left-0 w-1/5 bg-foreground animate-working-line"
        />
      )}
    </div>
  );
}

// "Thinking" is a state of the one working line, not a separate effect — this is
// a thin preset so call sites can read intent, without a duplicate implementation.
function ThinkingIndicator(props: Omit<WorkingIndicatorProps, "state">) {
  return <WorkingIndicator state="thinking" label={props.label ?? "Thinking…"} {...props} />;
}

export { WorkingIndicator, ThinkingIndicator };
