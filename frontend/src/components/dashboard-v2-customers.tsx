import { Users } from "lucide-react";
import Link from "next/link";
import { ActivityDot } from "@/components/ui/activity-dot";
import { Button } from "@/components/ui/button";
import { StatusPill } from "@/components/ui/status-pill";
import { STAGE_LABEL, STAGE_STATUS } from "@/lib/leads";
import type { Customer } from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

function customerName(customer: Customer): string {
  return customer.display_name || customer.company || customer.wa_phone || "Unknown customer";
}

// Dashboard V2's Recent Customers — surfacing people, not row counts.
// `customers` is `useCustomers({ limit })` (GET /api/v1/customers, a real
// endpoint V1's dashboard never called), fetched wider than shown and
// re-sorted by the page on real `last_message_at` (Sprint 88 dogfooding:
// the backend's own created_at ordering surfaced a customer who signed up
// recently but hadn't messaged in 50 days as "recent" — not who actually
// matters today). Every field shown is real: conversation_count and
// last_message_at come straight off Customer; the lead stage pill only
// renders when a real Lead is actually attached. No "AI summary" or
// relationship-health score is shown — neither exists on this data, and
// inventing one would violate the no-fake-data constraint this whole
// rebuild operates under.
//
// `variant="feed"` (used by the production Dashboard — default "list" keeps
// every existing caller byte-identical) reshapes the same rows into a
// messaging-app contact list: a larger avatar, the timestamp promoted to
// where a chat app puts it (top-right, next to the name), the lead stage
// demoted from a chip to a small meaningful dot so the row reads as a
// person, not a CRM record. Same data, same link, same empty-state icon —
// presentation only.
export function RecentCustomersPanel({
  customers,
  variant = "list",
}: {
  customers: Customer[];
  variant?: "list" | "feed";
}) {
  const isFeed = variant === "feed";

  return (
    <div className="h-full rounded-2xl bg-card p-6 shadow-e2 sm:p-7">
      <div className="mb-5 flex items-center justify-between">
        <h2 className="type-title">Recent customers</h2>
        <Button asChild size="sm" variant="ghost">
          <Link href="/customers">View all</Link>
        </Button>
      </div>

      {customers.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-8 text-center">
          <Users className="size-6 text-muted-foreground" aria-hidden="true" />
          <p className="text-sm text-muted-foreground">
            {isFeed
              ? "HIRA is waiting for your first conversation."
              : "No customers yet — new ones appear here as they come in."}
          </p>
        </div>
      ) : isFeed ? (
        <ul className="-mx-2.5">
          {customers.map((customer) => {
            const name = customerName(customer);
            return (
              <li key={customer.id}>
                <Link
                  href="/customers"
                  className="group flex items-center gap-3.5 rounded-xl px-2.5 py-3 transition-colors duration-150 hover:bg-accent/70 focus-visible:focus-ring"
                >
                  <div className="flex size-11 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary ring-1 ring-inset ring-border/40 transition-transform duration-150 group-hover:scale-105">
                    {initials(name)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-2">
                      <p className="truncate text-sm font-semibold">{name}</p>
                      {customer.last_message_at && (
                        <span className="shrink-0 text-[11px] text-muted-foreground">
                          {formatRelativeTime(customer.last_message_at)}
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">
                      {customer.conversation_count} {customer.conversation_count === 1 ? "conversation" : "conversations"}
                      {customer.lead && ` · ${STAGE_LABEL[customer.lead.stage]}`}
                    </p>
                  </div>
                  {customer.lead && (
                    <ActivityDot
                      state={STAGE_STATUS[customer.lead.stage]}
                      label={STAGE_LABEL[customer.lead.stage]}
                      className="mt-1 shrink-0"
                    />
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      ) : (
        <ul className="space-y-1">
          {customers.map((customer) => {
            const name = customerName(customer);
            return (
              <li key={customer.id}>
                <Link
                  href="/customers"
                  className="flex items-center gap-3 rounded-lg -mx-2 px-2 py-2.5 transition-colors hover:bg-accent"
                >
                  <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                    {initials(name)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{name}</p>
                    <p className="text-xs text-muted-foreground">
                      {customer.conversation_count} {customer.conversation_count === 1 ? "conversation" : "conversations"}
                      {customer.last_message_at && ` · Last interaction ${formatRelativeTime(customer.last_message_at)}`}
                    </p>
                  </div>
                  {customer.lead && (
                    <StatusPill state={STAGE_STATUS[customer.lead.stage]} className="shrink-0">
                      {STAGE_LABEL[customer.lead.stage]}
                    </StatusPill>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
