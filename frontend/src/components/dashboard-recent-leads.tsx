import { UserPlus } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusPill } from "@/components/ui/status-pill";
import { STAGE_LABEL, STAGE_STATUS } from "@/lib/leads";
import type { Lead } from "@/lib/types";
import { cn, formatRelativeTime } from "@/lib/utils";

function leadName(lead: Lead): string {
  return lead.customer.display_name || lead.customer.company || lead.customer.wa_phone || "Unknown lead";
}

// Same initials-avatar treatment as Today's Schedule and the Recent
// Activity timeline (Sprint 87) — one consistent "a row of people" language
// across every list-of-people panel on the page, instead of leads being the
// one list rendering as bare text rows.
function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

// Recent Leads (Sprint 86) — the page already fetches useLeads({ limit:
// PREVIEW_ROWS }) for the hero's "N new leads today" count, but the rows
// themselves went unused. This surfaces those same real rows instead of a
// second request.
//
// `polished` (Sprint 90, Dashboard V3 only — default false keeps V1's
// `/dashboard` byte-identical) tightens the row's hover/focus micro-
// interactions and softens the empty state copy. No layout or data change.
export function RecentLeadsCard({
  leads,
  className,
  polished = false,
}: {
  leads: Lead[];
  className?: string;
  polished?: boolean;
}) {
  return (
    <Card interactive className={cn("h-full", className)}>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="text-base">Recent leads</CardTitle>
        <Button asChild size="sm" variant="ghost">
          <Link href="/leads">View all</Link>
        </Button>
      </CardHeader>
      <CardContent>
        {leads.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-8 text-center">
            <UserPlus className="size-6 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">
              {polished
                ? "No leads yet — HIRA will log them here the moment one comes in."
                : "No leads yet — new ones appear here as they come in."}
            </p>
          </div>
        ) : (
          <ul className="space-y-1">
            {leads.map((lead) => {
              const name = leadName(lead);
              return (
                <li key={lead.id}>
                  <Link
                    href="/leads"
                    className={cn(
                      "flex items-center gap-3 rounded-lg -mx-2 px-2 py-2 transition-colors duration-150 hover:bg-accent",
                      polished && "focus-visible:focus-ring",
                    )}
                  >
                    <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                      {initials(name)}
                    </div>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{name}</span>
                      <span className="text-xs text-muted-foreground">
                        Last interaction {formatRelativeTime(lead.updated_at)}
                      </span>
                    </span>
                    <span className="flex shrink-0 flex-col items-end gap-1">
                      <StatusPill state={STAGE_STATUS[lead.stage]}>{STAGE_LABEL[lead.stage]}</StatusPill>
                      {lead.estimated_value !== null && (
                        <span className="text-xs font-semibold tabular-nums text-muted-foreground">
                          ${lead.estimated_value.toLocaleString()}
                        </span>
                      )}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
