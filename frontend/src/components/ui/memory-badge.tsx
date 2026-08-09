import { BookOpen } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";

// Marks that something is now part of HIRA's permanent knowledge — a new
// entry learned from a conversation, or an existing one a draft drew on
// (DESIGN-MOTION-001 §6.7: "learning is permanent and visible"). Distinct
// from EvidenceCard (a full grounding citation with a source + snippet):
// this is the compact inline marker for a list row, activity item, or
// message bubble where a full card is too heavy. Same BookOpen icon as
// EvidenceCard so the two read as one visual language for "knowledge."
export interface MemoryBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** Defaults to "Learned"; pass e.g. "Grounded in 3 sources" to override. */
  children?: React.ReactNode;
}

function MemoryBadge({ children, className, ...props }: MemoryBadgeProps) {
  return (
    <span
      className={cn(
        "type-caption inline-flex items-center gap-1.5 rounded-full border border-brand/25 bg-brand/10 px-2.5 py-0.5 font-medium text-brand",
        className,
      )}
      {...props}
    >
      <BookOpen className="size-3" aria-hidden />
      {children ?? "Learned"}
    </span>
  );
}

export { MemoryBadge };
