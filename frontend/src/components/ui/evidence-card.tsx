import * as React from "react";
import { cn } from "@/lib/utils";
import { aiSurfaceClassName } from "./ai-surface";

// A grounding-evidence chip (DESIGN-MOTION-001 §6.4): the source a reply is
// grounded in — shown BEFORE the conclusion, so "the AI looked it up" reads
// instead of "the AI made it up". Sits on the AI surface. Generic; not wired
// into a screen yet.
interface EvidenceCardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Where the evidence came from, e.g. a knowledge-base entry title. */
  source: string;
  /** Optional leading icon (a lucide icon element, etc.). */
  icon?: React.ReactNode;
  /** Optional supporting snippet. */
  children?: React.ReactNode;
}

function EvidenceCard({ source, icon, children, className, ...props }: EvidenceCardProps) {
  return (
    <div className={cn(aiSurfaceClassName, "flex gap-2 p-3", className)} {...props}>
      {icon && (
        <span aria-hidden className="mt-0.5 shrink-0 text-muted-foreground [&_svg]:size-4">
          {icon}
        </span>
      )}
      <div className="min-w-0 space-y-0.5">
        <p className="type-caption truncate font-medium text-foreground">{source}</p>
        {children && <p className="type-caption text-muted-foreground">{children}</p>}
      </div>
    </div>
  );
}

export { EvidenceCard };
