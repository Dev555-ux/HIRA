"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";

// A minimal, dependency-free tooltip (DESIGN-MOTION-001 §10.30–31: open delay
// so passing the cursor over a row of controls doesn't flicker a tooltip per
// control; a short "warm" window so hopping between adjacent controls after
// the first tooltip has opened skips the delay). No @radix-ui/react-tooltip —
// this project's standing preference is zero new runtime dependencies for
// what a few lines of state can do (see the zero-dependency motion approach
// in globals.css), and a single-axis hover/focus popup doesn't need one.
//
// Portaled to document.body (react-dom, not a new dependency) rather than
// positioned via a `relative` wrapper: a trigger that lives inside a clipped
// scroll container — e.g. the collapsed sidebar's `overflow-y-auto` nav rail
// — would otherwise cut the tooltip off at the container's edge. Position is
// computed from the trigger's own getBoundingClientRect() on open.

const OPEN_DELAY_MS = 400;
const CLOSE_DELAY_MS = 100;
const WARM_WINDOW_MS = 600;
const GAP_PX = 6;

let lastClosedAt = 0;

type TriggerProps = React.HTMLAttributes<HTMLElement> & Record<string, unknown>;

export interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactElement<TriggerProps>;
  side?: "top" | "bottom" | "left" | "right";
  className?: string;
}

// Fixed-position coords (viewport-relative, matching getBoundingClientRect —
// no scroll-offset math needed) plus the transform that anchors the
// tooltip's own edge/center to that point.
const SIDE_TRANSFORM: Record<NonNullable<TooltipProps["side"]>, string> = {
  top: "-translate-x-1/2 -translate-y-full",
  bottom: "-translate-x-1/2",
  left: "-translate-x-full -translate-y-1/2",
  right: "-translate-y-1/2",
};

function Tooltip({ content, children, side = "top", className }: TooltipProps) {
  const [open, setOpen] = React.useState(false);
  const [coords, setCoords] = React.useState<{ top: number; left: number } | null>(null);
  const id = React.useId();
  const wrapperRef = React.useRef<HTMLSpanElement>(null);
  const openTimer = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const closeTimer = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const measure = React.useCallback(() => {
    const rect = wrapperRef.current?.getBoundingClientRect();
    if (!rect) return;
    switch (side) {
      case "right":
        setCoords({ top: rect.top + rect.height / 2, left: rect.right + GAP_PX });
        break;
      case "left":
        setCoords({ top: rect.top + rect.height / 2, left: rect.left - GAP_PX });
        break;
      case "bottom":
        setCoords({ top: rect.bottom + GAP_PX, left: rect.left + rect.width / 2 });
        break;
      case "top":
      default:
        setCoords({ top: rect.top - GAP_PX, left: rect.left + rect.width / 2 });
        break;
    }
  }, [side]);

  const show = React.useCallback(() => {
    window.clearTimeout(closeTimer.current);
    const warm = Date.now() - lastClosedAt < WARM_WINDOW_MS;
    openTimer.current = setTimeout(
      () => {
        measure();
        setOpen(true);
      },
      warm ? 0 : OPEN_DELAY_MS,
    );
  }, [measure]);

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

  // The trigger can scroll (or the viewport can resize) while the tooltip
  // is open — re-measure rather than leave it pinned to a stale position.
  React.useEffect(() => {
    if (!open) return;
    window.addEventListener("scroll", measure, true);
    window.addEventListener("resize", measure);
    return () => {
      window.removeEventListener("scroll", measure, true);
      window.removeEventListener("resize", measure);
    };
  }, [open, measure]);

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
      measure();
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
    <span ref={wrapperRef} className="inline-block">
      {child}
      {open &&
        coords &&
        createPortal(
          <span
            role="tooltip"
            id={id}
            className={cn(
              "type-caption pointer-events-none fixed z-[var(--z-popover)] whitespace-nowrap rounded-md bg-foreground px-2 py-1 text-background shadow-e2 animate-fade-in",
              SIDE_TRANSFORM[side],
              className,
            )}
            style={{ top: coords.top, left: coords.left }}
          >
            {content}
          </span>,
          document.body,
        )}
    </span>
  );
}

export { Tooltip };
