import * as React from "react";
import { cn } from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        ref={ref}
        className={cn(
          // IMPLEMENTATION-ROADMAP-001 M2: two-layer focus ring, reusing M1's
          // finalized Button values verbatim — the existing ring-2/ring-ring
          // (box-shadow) is unchanged, joined by a separate `outline` layer
          // for the softer outer halo. outline-none is dropped for the same
          // reason it was in Button: the outline is now explicitly styled,
          // not suppressed.
          "flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors duration-[var(--motion-fast)] placeholder:text-muted-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring/30 focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
        {...props}
      />
    );
  },
);
Input.displayName = "Input";

export { Input };
