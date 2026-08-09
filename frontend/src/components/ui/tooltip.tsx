"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

// A minimal, dependency-free tooltip (DESIGN-MOTION-001 §10.30–31: open delay
// so passing the cursor over a row of controls doesn't flicker a tooltip per
// control; a short "warm" window so hopping between adjacent controls after
// the first tooltip has opened skips the delay). No @radix-ui/react-tooltip —
// this project's standing preference is zero new runtime dependencies for
// what a few lines of state can do (see the zero-dependency motion approach
// in globals.css), and a single-axis hover/focus popup doesn't need one.
//
// Wraps its child in a positioning span and clones the open/close handlers
// onto the child itself, so aria-describedby lands on the actual focusable
// element (the thing a screen reader has focus on), not an inert wrapper.

const OPEN_DELAY_MS = 400;
const CLOSE_DELAY_MS = 100;
const WARM_WINDOW_MS = 600;

let lastClosedAt = 0;

type TriggerProps = React.HTMLAttributes<HTMLElement> & Record<string, unknown>;

export interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactElement<TriggerProps>;
  side?: "top" | "bottom" | "left" | "right";
  className?: string;
}

const SIDE_CLASSES: Record<NonNullable<TooltipProps["side"]>, string> = {
  top: "bottom-full left-1/2 mb-1.5 -translate-x-1/2",
  bottom: "top-full left-1/2 mt-1.5 -translate-x-1/2",
  left: "right-full top-1/2 mr-1.5 -translate-y-1/2",
  right: "left-full top-1/2 ml-1.5 -translate-y-1/2",
};

function Tooltip({ content, children, side = "top", className }: TooltipProps) {
  const [open, setOpen] = React.useState(false);
  const id = React.useId();
  const openTimer = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const closeTimer = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const show = React.useCallback(() => {
    window.clearTimeout(closeTimer.current);
    const warm = Date.now() - lastClosedAt < WARM_WINDOW_MS;
    openTimer.current = setTimeout(() => setOpen(true), warm ? 0 : OPEN_DELAY_MS);
  }, []);

  const hide = React.useCallback((immediate = false) => {
    window.clearTimeout(openTimer.current);
    closeTimer.current = setTimeout(
      () => {
        setOpen(false);
        lastClosedAt = Date.now();
      },
      immediate ? 0 : CLOSE_DELAY_MS,
    );
  }, []);

  React.useEffect(
    () => () => {
      window.clearTimeout(openTimer.current);
      window.clearTimeout(closeTimer.current);
    },
    [],
  );

  const child = React.cloneElement(children, {
    "aria-describedby": open ? id : undefined,
    onMouseEnter: (e: React.MouseEvent<HTMLElement>) => {
      children.props.onMouseEnter?.(e);
      show();
    },
    onMouseLeave: (e: React.MouseEvent<HTMLElement>) => {
      children.props.onMouseLeave?.(e);
      hide();
    },
    onFocus: (e: React.FocusEvent<HTMLElement>) => {
      children.props.onFocus?.(e);
      setOpen(true);
    },
    onBlur: (e: React.FocusEvent<HTMLElement>) => {
      children.props.onBlur?.(e);
      hide(true);
    },
    onKeyDown: (e: React.KeyboardEvent<HTMLElement>) => {
      children.props.onKeyDown?.(e);
      if (e.key === "Escape") hide(true);
    },
  } as Partial<Record<string, unknown>>);

  return (
    <span className="relative inline-block">
      {child}
      {open && (
        <span
          role="tooltip"
          id={id}
          className={cn(
            "type-caption pointer-events-none absolute z-[var(--z-popover)] whitespace-nowrap rounded-md bg-foreground px-2 py-1 text-background shadow-e2 animate-fade-in",
            SIDE_CLASSES[side],
            className,
          )}
        >
          {content}
        </span>
      )}
    </span>
  );
}

export { Tooltip };
