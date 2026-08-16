import { CheckCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn, formatRelativeTime } from "@/lib/utils";

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

// Sprint 89 — the priority dot each inbox row leads with. Same
// destructive/warning distinction as the badge variant above, just a
// quieter mark than a full chip once every row is single-line.
const PRIORITY_DOT: Record<AttentionPriority, string> = {
  high: "bg-destructive",
  medium: "bg-warning",
};

// Dashboard V2's Needs Attention — an executive task queue: priority, what
// it is, why it's here, and one quick action, every field real (priority is
// derived from the same destructive/warning distinction V1's ALERT_TONE
// already draws, not an invented severity score). `items` is assembled by
// the page from three real sources — pending replies, open escalations,
// business-health alerts — the same three V1's Needs Attention already
// merges.
//
// `variant="inbox"` (used by the production Dashboard — default "panel" keeps
// every existing caller byte-identical) reshapes the same data into a
// mail-client reading: single-line rows separated by hairlines instead of
// padded task cards, a priority dot standing in for the badge chip, the
// action revealed on hover instead of always visible. Same items, same
// onAction handlers — presentation only.
export function AttentionQueue({
  items,
  variant = "panel",
}: {
  items: AttentionItem[];
  variant?: "panel" | "inbox";
}) {
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

  const isInbox = variant === "inbox";

  return (
    <div className="h-full rounded-2xl bg-card p-6 shadow-e2 sm:p-7">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="type-title">Needs your attention</h2>
        <span className="text-xs text-muted-foreground">
          {items.length} {isInbox ? "open" : items.length === 1 ? "item" : "items"}
        </span>
      </div>

      {isInbox ? (
        <ul className="-mx-2 divide-y divide-border/60">
          {items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                onClick={item.onAction}
                className="group/row flex w-full items-center gap-3 rounded-lg px-2 py-3 text-left transition-colors duration-150 hover:bg-accent/60 focus-visible:focus-ring"
              >
                <span
                  className={cn("size-1.5 shrink-0 rounded-full", PRIORITY_DOT[item.priority])}
                  aria-hidden="true"
                />
                <span className="min-w-0 flex-1 truncate text-sm">
                  <span className="font-semibold">{item.title}</span>
                  <span className="text-muted-foreground"> — {item.reason}</span>
                </span>
                {/* Time and action share one grid cell and crossfade on
                    hover/focus, rather than swapping display — the row's
                    trailing edge never jumps width mid-hover. */}
                <span className="relative grid h-4 w-16 shrink-0 place-items-end">
                  <span className="col-start-1 row-start-1 text-[11px] text-muted-foreground transition-opacity duration-150 group-hover/row:opacity-0 group-focus-visible/row:opacity-0">
                    {formatRelativeTime(item.createdAt)}
                  </span>
                  <span className="col-start-1 row-start-1 text-xs font-semibold text-brand opacity-0 transition-opacity duration-150 group-hover/row:opacity-100 group-focus-visible/row:opacity-100">
                    {item.actionLabel} →
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <ul className="space-y-1">
          {items.map((item) => {
            const badge = PRIORITY_BADGE[item.priority];
            return (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={item.onAction}
                  className="flex w-full items-start gap-3 rounded-xl px-3 py-3 text-left transition-colors duration-150 hover:bg-accent focus-visible:focus-ring"
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
      )}
    </div>
  );
}
