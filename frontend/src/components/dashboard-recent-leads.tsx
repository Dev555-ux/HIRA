import { UserPlus } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusPill } from "@/components/ui/status-pill";
import { STAGE_LABEL, STAGE_STATUS } from "@/lib/leads";
import type { Lead } from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";

function leadName(lead: Lead): string {
  return lead.customer.display_name || lead.customer.company || lead.customer.wa_phone || "Unknown lead";
}

// Recent Leads (Sprint 86) — the page already fetches useLeads({ limit:
// PREVIEW_ROWS }) for the hero's "N new leads today" count, but the rows
// themselves went unused. This surfaces those same real rows instead of a
// second request.
export function RecentLeadsCard({ leads }: { leads: Lead[] }) {
  return (
    <Card interactive>
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
            <p className="text-sm text-muted-foreground">No leads yet — new ones appear here as they come in.</p>
          </div>
        ) : (
          <ul className="space-y-3.5">
            {leads.map((lead) => (
              <li key={lead.id}>
                <Link
                  href="/leads"
                  className="flex items-center justify-between gap-3 rounded-md -mx-2 px-2 py-1 hover:bg-accent"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{leadName(lead)}</span>
                    <span className="text-xs text-muted-foreground">{formatRelativeTime(lead.created_at)}</span>
                  </span>
                  <StatusPill state={STAGE_STATUS[lead.stage]} className="shrink-0">
                    {STAGE_LABEL[lead.stage]}
                  </StatusPill>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
