import { CheckCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { formatRelativeTime } from "@/lib/utils";

export type AttentionPriority = "high" | "medium";

export interface AttentionItem {
  id: string;
  priority: AttentionPriority;
  title: string;
  reason: string;
  actionLabel: string;
  createdAt: string;
  onAction: () => void;
}

const PRIORITY_BADGE: Record<AttentionPriority, { label: string; variant: "destructive" | "warning" }> = {
  high: { label: "High", variant: "destructive" },
  medium: { label: "Medium", variant: "warning" },
};

// Dashboard V2's Needs Attention — an executive task queue, not a stack of
// warning cards: priority, what it is, why it's here, and one quick action,
// every field real (priority is derived from the same destructive/warning
// distinction V1's ALERT_TONE already draws, not an invented severity
// score). `items` is assembled by the page from three real sources —
// pending replies, open escalations, business-health alerts — the same
// three V1's Needs Attention already merges.
export function AttentionQueue({ items }: { items: AttentionItem[] }) {
  if (items.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 rounded-2xl bg-card p-10 text-center shadow-e2">
        <CheckCheck className="size-6 text-success" aria-hidden="true" />
        <p className="text-sm font-medium">Nothing needs you right now</p>
        <p className="max-w-xs text-sm text-muted-foreground">
          Approvals, escalated conversations, and account issues will show up here the moment something needs a
          decision.
        </p>
      </div>
    );
  }

  return (
    <div className="h-full rounded-2xl bg-card p-6 shadow-e2 sm:p-7">
      <div className="mb-5 flex items-center justify-between">
        <h2 className="type-title">Needs your attention</h2>
        <span className="text-xs text-muted-foreground">
          {items.length} {items.length === 1 ? "item" : "items"}
        </span>
      </div>
      <ul className="space-y-1">
        {items.map((item) => {
          const badge = PRIORITY_BADGE[item.priority];
          return (
            <li key={item.id}>
              <button
                type="button"
                onClick={item.onAction}
                className="flex w-full items-start gap-3 rounded-xl px-3 py-3 text-left transition-colors hover:bg-accent"
              >
                <Badge variant={badge.variant} className="mt-0.5 shrink-0">
                  {badge.label}
                </Badge>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{item.title}</p>
                  <p className="truncate text-xs text-muted-foreground">{item.reason}</p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  <span className="text-xs font-medium text-foreground underline-offset-4 group-hover:underline">
                    {item.actionLabel}
                  </span>
                  <span className="text-[11px] text-muted-foreground">{formatRelativeTime(item.createdAt)}</span>
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
