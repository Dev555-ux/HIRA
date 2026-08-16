import { Users } from "lucide-react";
import Link from "next/link";
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
// `customers` is `useCustomers({ limit })` (ordered newest-first by the
// backend, GET /api/v1/customers), a real endpoint V1's dashboard never
// called. Every field shown is real: conversation_count and
// last_message_at come straight off Customer; the lead stage pill only
// renders when a real Lead is actually attached. No "AI summary" or
// relationship-health score is shown — neither exists on this data, and
// inventing one would violate the no-fake-data constraint this whole
// rebuild operates under.
export function RecentCustomersPanel({ customers }: { customers: Customer[] }) {
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
          <p className="text-sm text-muted-foreground">No customers yet — new ones appear here as they come in.</p>
        </div>
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
