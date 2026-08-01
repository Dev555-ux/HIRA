"use client";

import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import * as React from "react";
import { cn } from "@/lib/utils";

// 300ms rather than Radix's 700ms default: these sit on icon-only buttons
// where the tooltip is the only thing naming the action, so waiting most of
// a second to learn what a button does is too slow — but instant would make
// the label flicker as the pointer crosses a toolbar on its way elsewhere.
const TooltipProvider = ({
  delayDuration = 300,
  ...props
}: React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Provider>) => (
  <TooltipPrimitive.Provider delayDuration={delayDuration} {...props} />
);

const Tooltip = TooltipPrimitive.Root;
const TooltipTrigger = TooltipPrimitive.Trigger;

const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 6, ...props }, ref) => (
  <TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      // Reuses the popover keyframes rather than adding tooltip-specific
      // ones — same surface class of transient floating layer, and the
      // global prefers-reduced-motion guard already covers them.
      className={cn(
        "z-50 overflow-hidden rounded-md border bg-popover px-2.5 py-1.5 text-xs text-popover-foreground shadow-md data-[state=delayed-open]:animate-popover-show data-[state=closed]:animate-popover-hide",
        className,
      )}
      {...props}
    />
  </TooltipPrimitive.Portal>
));
TooltipContent.displayName = "TooltipContent";

/**
 * The common case: naming an icon-only control on hover/focus.
 *
 * `label` is the visible tooltip text only — the child keeps its own
 * `aria-label`, which stays the element's accessible name. Radix wires the
 * tooltip up as `aria-describedby`, so this adds a visual affordance for
 * sighted pointer users without changing what assistive tech announces (and
 * without changing what `getByRole("button", { name })` resolves to).
 */
function IconTooltip({
  label,
  side,
  children,
}: {
  label: string;
  side?: React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>["side"];
  children: React.ReactNode;
}) {
  return (
    // Carries its own Provider rather than depending on an app-root one.
    // Radix throws outright when a Tooltip has no Provider ancestor, which
    // would make every component containing an icon button un-renderable in
    // isolation — the existing tests call RTL's `render` directly with no
    // app-provider wrapper, and a primitive that works or crashes depending
    // on where it happens to be mounted is a bad primitive regardless.
    //
    // The cost is Radix's cross-tooltip grouping: skipDelayDuration only
    // applies within a single Provider, so moving between two adjacent icon
    // buttons re-incurs the 300ms delay instead of showing instantly. That's
    // a fair trade at our scale — icon groups here are pairs (edit/delete,
    // approve/reject), not dense toolbars.
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>{children}</TooltipTrigger>
        <TooltipContent side={side}>{label}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider, IconTooltip };
