import { X } from "lucide-react";
import * as React from "react";
import { aiSurfaceClassName } from "./ai-surface";
import { Button } from "./button";
import { cn } from "@/lib/utils";

// A suggestion HIRA is making, not a task the founder created — always
// AI-authored, so it always sits on the AI surface (§4.4 spine). Distinct
// from TaskCard: a recommendation is proposed and can be dismissed; a task
// is already committed to. Silence over explanation (per the component
// brief) — one sentence of reasoning, one primary action, one dismiss.
export interface RecommendationCardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  accept?: { label: string; onClick: () => void };
  onDismiss?: () => void;
}

function RecommendationCard({
  children,
  accept,
  onDismiss,
  className,
  ...props
}: RecommendationCardProps) {
  return (
    <div className={cn(aiSurfaceClassName, "space-y-3 p-4", className)} {...props}>
      <div className="flex items-start justify-between gap-2">
        <p className="type-body text-foreground">{children}</p>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss recommendation"
            className="shrink-0 text-muted-foreground opacity-70 transition-opacity hover:opacity-100"
          >
            <X className="size-4" />
          </button>
        )}
      </div>
      {accept && (
        <Button size="sm" onClick={accept.onClick}>
          {accept.label}
        </Button>
      )}
    </div>
  );
}

export { RecommendationCard };
