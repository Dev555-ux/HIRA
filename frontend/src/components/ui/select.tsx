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
          "flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive aria-invalid:focus-visible:ring-destructive",
          className,
        )}
        {...props}
      />
    );
  },
);
Select.displayName = "Select";

export { Select };
