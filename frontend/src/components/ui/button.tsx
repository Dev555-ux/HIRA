import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  // Sprint 46: box-shadow joined the transitioned properties so the
  // focus-visible ring (a box-shadow under the hood) and the outline hover
  // shadow both settle in smoothly instead of snapping on.
  //
  // IMPLEMENTATION-ROADMAP-001 M1: the focus ring is now two independent
  // layers — the original ring-* utilities (box-shadow-based) stay exactly
  // as they were, joined by a separate `outline` layer for the softer outer
  // halo. `outline` is a distinct CSS property from `box-shadow`, so it can
  // never fight the existing ring/ring-offset/shadow-e* stack (no more
  // `focus-visible:outline-none` needed either — with the outline now
  // explicitly styled instead of suppressed, there's nothing left to hide).
  // `outline-color` joins the transitioned properties for the same
  // smooth-settle reason box-shadow already does.
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-[color,background-color,border-color,box-shadow,outline-color,transform] duration-[var(--motion-fast)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring/30 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 active:scale-[0.98] [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        // Hover lift (M1): a 1px rise alongside the shadow escalation these
        // three variants already had. Scoped to only the variants that
        // already paired a hover state with a shadow change — secondary/
        // ghost/link never had that pairing, so they're left exactly as
        // they were rather than gaining a lift with no shadow to reinforce
        // it (DESIGN-SCREENBOOK-002 §2's refinement is additive, not a
        // license to change every variant's hover behavior).
        default:
          "bg-primary text-primary-foreground hover:bg-primary/90 shadow-e1 hover:shadow-e2 hover:-translate-y-px active:translate-y-0",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90 shadow-e1 hover:shadow-e2 hover:-translate-y-px active:translate-y-0",
        outline:
          "border border-input bg-background hover:bg-accent hover:text-accent-foreground hover:shadow-e1 hover:-translate-y-px active:translate-y-0",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-md px-6",
        // Landing-page-weight CTA (Hero, FinalCta) — every other size stays
        // exactly as it was, so no existing call site anywhere else changes.
        xl: "h-12 rounded-lg px-8 text-base font-semibold",
        icon: "size-9",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
