import { AlertTriangle, CheckCheck, MessageSquare } from "lucide-react";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { AiActivityCustomer, AiActivityEntry, AiActivityOutcome } from "@/lib/types";
import { cn, formatRelativeTime } from "@/lib/utils";

const CATEGORY_LABEL: Record<AiActivityEntry["category"], string> = {
  conversation: "Conversation",
  capability: "Capability",
  knowledge: "Knowledge",
  action: "Action",
};

const OUTCOME_BADGE: Record<AiActivityOutcome, { label: string; variant: NonNullable<BadgeProps["variant"]> }> = {
  sent: { label: "Sent", variant: "success" },
  pending_approval: { label: "Pending", variant: "secondary" },
  sending: { label: "Sending", variant: "secondary" },
  rejected: { label: "Rejected", variant: "warning" },
  escalated: { label: "Escalated", variant: "warning" },
  failed: { label: "Failed", variant: "destructive" },
};

function activityIcon(outcome: AiActivityOutcome): typeof CheckCheck {
  if (outcome === "escalated" || outcome === "failed") return AlertTriangle;
  if (outcome === "pending_approval" || outcome === "sending" || outcome === "rejected") return MessageSquare;
  return CheckCheck;
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

// The leading visual per row — a customer's initials when the activity has a
// real customer attached (most rows do), falling back to the outcome icon
// for system-level entries (e.g. a capability/knowledge action with no
// customer). One consistent tone (not a per-name color palette) so the
// outcome badge, not the avatar, is what actually carries meaning.
function ActivityAvatar({ customer, outcome }: { customer: AiActivityCustomer | null; outcome: AiActivityOutcome }) {
  if (customer?.display_name) {
    return (
      <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
        {initials(customer.display_name)}
      </div>
    );
  }
  const Icon = activityIcon(outcome);
  return (
    <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10">
      <Icon className="size-4 text-primary" aria-hidden="true" />
    </div>
  );
}

// Recent Activity timeline (Sprint 86) — promotes the old plain "AI
// activity" list (icon + truncated summary + timestamp) into a wide,
// premium timeline: a customer avatar (or outcome icon when there's no
// customer), the category, and an outcome badge alongside the timestamp.
// Same AiActivityEntry data as before — no fabricated fields, no invented
// activity types (e.g. no "Calendar synced": calendar actions already
// arrive as real booked/rescheduled/cancelled-appointment summaries under
// category "action").
export function ActivityTimeline({ entries }: { entries: AiActivityEntry[] }) {
  return (
    <ul className="divide-y" data-testid="activity-feed">
      {entries.map((entry) => {
        const badge = OUTCOME_BADGE[entry.outcome];
        return (
          <li key={entry.id} className="group flex items-center gap-3.5 px-6 py-3.5">
            <ActivityAvatar customer={entry.customer} outcome={entry.outcome} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{entry.summary}</p>
              <p className={cn("text-xs text-muted-foreground")}>{CATEGORY_LABEL[entry.category]}</p>
            </div>
            <Badge variant={badge.variant} className="shrink-0">
              {badge.label}
            </Badge>
            <span className="shrink-0 text-xs text-muted-foreground">{formatRelativeTime(entry.created_at)}</span>
          </li>
        );
      })}
    </ul>
  );
}
