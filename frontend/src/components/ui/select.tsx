import * as React from "react";
import { cn } from "@/lib/utils";

// A plain native <select>, styled to match Input — no @radix-ui/react-select
// dependency (not installed; see DEC-031's scope discipline on new deps).
const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, ...props }, ref) => {
    return (
      <select
        ref={ref}
        className={cn(
          // IMPLEMENTATION-ROADMAP-001 M2 — same two-layer ring as Input.
          "flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors duration-[var(--motion-fast)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring/30 focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
        {...props}
      />
    );
  },
);
Select.displayName = "Select";

export { Select };
