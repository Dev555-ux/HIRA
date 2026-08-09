import * as React from "react";
import { cardClassName } from "./card";
import { cn } from "@/lib/utils";

// A generic actionable item — a founder to-do, a follow-up, a next step
// surfaced on Home. Neutral by default (a task can originate from a founder
// or from HIRA); pass `aiAuthored` to render it on the AI surface instead
// when HIRA itself is the one suggesting it.
export interface TaskCardProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  title: React.ReactNode;
  description?: React.ReactNode;
  /** e.g. a due-date chip, an assignee name — rendered as a small trailing row. */
  meta?: React.ReactNode;
  action?: { label: string; onClick: () => void };
  aiAuthored?: boolean;
}

function TaskCard({
  title,
  description,
  meta,
  action,
  aiAuthored = false,
  className,
  ...props
}: TaskCardProps) {
  return (
    <div
      className={cn(
        aiAuthored
          ? "rounded-lg border border-l-2 border-border border-l-brand bg-ai text-ai-foreground shadow-e1"
          : cardClassName,
        "flex items-start justify-between gap-3 p-4",
        className,
      )}
      {...props}
    >
      <div className="min-w-0 space-y-1">
        <p className="type-title text-sm">{title}</p>
        {description && <p className="type-caption text-muted-foreground">{description}</p>}
        {meta && <div className="pt-1">{meta}</div>}
      </div>
      {action && (
        <button
          type="button"
          onClick={action.onClick}
          className="type-caption shrink-0 rounded-md px-2.5 py-1 font-medium text-foreground underline-offset-4 hover:bg-accent hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring/30"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}

export { TaskCard };
