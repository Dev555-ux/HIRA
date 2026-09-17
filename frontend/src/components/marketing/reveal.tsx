"use client";

import * as React from "react";
import { useInView } from "@/hooks/use-in-view";
import { cn } from "@/lib/utils";

// Wraps a marketing section's content div so it enters via `fade-in-up` the
// first time it scrolls into view (DESIGN-MOTION-001 §7.5) instead of being
// present on load — content is never hidden from anyone (no-JS, reduced
// motion, and older browsers all render it immediately visible via
// useInView's fallback), only newly-visible content gets the entrance.
export const Reveal = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  function Reveal({ className, children, ...props }, forwardedRef) {
    const { ref, inView } = useInView<HTMLDivElement>();
    return (
      <div
        ref={(node) => {
          (ref as React.MutableRefObject<HTMLDivElement | null>).current = node;
          if (typeof forwardedRef === "function") forwardedRef(node);
          else if (forwardedRef) forwardedRef.current = node;
        }}
        // data-reveal marks "starts hidden, revealed by JS" — the noscript rule
        // in app/layout.tsx targets it so this content is visible without JS.
        data-reveal
        className={cn(className, inView ? "animate-fade-in-up" : "opacity-0")}
        {...props}
      >
        {children}
      </div>
    );
  },
);
