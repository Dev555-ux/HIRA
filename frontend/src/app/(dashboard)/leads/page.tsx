"use client";

import { AlertTriangle, RefreshCw, Search, Target } from "lucide-react";
import { useState } from "react";
import { CustomerDetailPane } from "@/components/customer-detail";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { useLeads } from "@/hooks/use-leads";
import { STAGE_BADGE_VARIANT, STAGE_LABEL, LEAD_STAGES } from "@/lib/leads";
import type { Lead, LeadStage } from "@/lib/types";
import { cn, formatRelativeTime } from "@/lib/utils";

const PAGE_SIZE = 20;

const STAGE_FILTERS: { label: string; value: LeadStage | undefined }[] = [
  { label: "All", value: undefined },
  ...LEAD_STAGES.map((s) => ({ label: s.label, value: s.value })),
];

export default function LeadsPage() {
  const [query, setQuery] = useState("");
  const [stage, setStage] = useState<LeadStage | undefined>(undefined);
  const [offset, setOffset] = useState(0);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null);
  const debouncedQuery = useDebouncedValue(query);

  const { data, isLoading, isError, error, isFetching, refetch } = useLeads({
    search: debouncedQuery || undefined,
    stage,
    limit: PAGE_SIZE,
    offset,
  });
  const leads = data?.data ?? [];
  const total = data?.meta.total ?? 0;

  function handleSearchChange(value: string) {
    setQuery(value);
    setOffset(0);
  }

  function handleStageChange(value: LeadStage | undefined) {
    setStage(value);
    setOffset(0);
  }

  return (
    <>
      <PageHeader
        title="Leads"
        description="Your sales pipeline, grouped by stage."
        action={
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className={isFetching ? "animate-spin" : ""} />
            Refresh
          </Button>
        }
      />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative max-w-sm flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search leads…"
            value={query}
            onChange={(e) => handleSearchChange(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap gap-1">
          {STAGE_FILTERS.map((f) => (
            <Button
              key={f.label}
              size="sm"
              variant={stage === f.value ? "secondary" : "ghost"}
              onClick={() => handleStageChange(f.value)}
            >
              {f.label}
            </Button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <LeadList
          leads={leads}
          isLoading={isLoading}
          isError={isError}
          error={error}
          onRetry={refetch}
          selectedCustomerId={selectedCustomerId}
          onSelect={setSelectedCustomerId}
          hasQuery={query.length > 0 || stage !== undefined}
          total={total}
          offset={offset}
          onOffsetChange={setOffset}
        />
        <CustomerDetailPane
          customerId={selectedCustomerId}
          onBack={() => setSelectedCustomerId(null)}
        />
      </div>
    </>
  );
}

function LeadList({
  leads,
  isLoading,
  isError,
  error,
  onRetry,
  selectedCustomerId,
  onSelect,
  hasQuery,
  total,
  offset,
  onOffsetChange,
}: {
  leads: Lead[];
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  onRetry: () => void;
  selectedCustomerId: string | null;
  onSelect: (customerId: string) => void;
  hasQuery: boolean;
  total: number;
  offset: number;
  onOffsetChange: (offset: number) => void;
}) {
  return (
    <Card
      className={cn(
        "flex min-h-[420px] flex-col",
        selectedCustomerId !== null ? "hidden lg:flex" : "flex",
      )}
    >
      <CardContent className="flex-1 p-0">
        {isLoading && (
          <div className="space-y-3 p-4">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        )}

        {isError && (
          <EmptyState
            icon={AlertTriangle}
            title="Couldn't load leads"
            description={error instanceof Error ? error.message : "Something went wrong."}
            action={
              <Button size="sm" onClick={onRetry}>
                Retry
              </Button>
            }
            className="border-0 py-16"
          />
        )}

        {!isLoading && !isError && leads.length === 0 && (
          <EmptyState
            icon={Target}
            title={hasQuery ? "No matches" : "No leads yet"}
            description={
              hasQuery
                ? "Try a different search term or stage."
                : "Leads logged from the Customers page, or by the AI during a conversation, will show up here."
            }
            className="border-0 py-16"
          />
        )}

        {!isLoading && !isError && leads.length > 0 && (
          <ul className="divide-y">
            {leads.map((lead) => (
              <li key={lead.id}>
                <button
                  type="button"
                  onClick={() => onSelect(lead.customer.id)}
                  className={cn(
                    "flex w-full flex-col gap-1 px-4 py-3 text-left transition-colors hover:bg-accent/50",
                    selectedCustomerId === lead.customer.id && "bg-accent",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium">
                      {lead.customer.display_name || lead.customer.wa_phone}
                    </span>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {formatRelativeTime(lead.updated_at)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={STAGE_BADGE_VARIANT[lead.stage]}>
                      {STAGE_LABEL[lead.stage]}
                    </Badge>
                    {lead.estimated_value !== null && (
                      <span className="text-xs text-muted-foreground">
                        ${lead.estimated_value.toLocaleString()}
                      </span>
                    )}
                  </div>
                  {lead.next_follow_up_at && (
                    <p className="truncate text-xs text-muted-foreground">
                      Follow up {formatRelativeTime(lead.next_follow_up_at)}
                    </p>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between border-t px-4 py-3 text-xs text-muted-foreground">
          <span>
            {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
          </span>
          <div className="flex gap-1">
            <Button
              variant="outline"
              size="sm"
              disabled={offset === 0}
              onClick={() => onOffsetChange(Math.max(0, offset - PAGE_SIZE))}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => onOffsetChange(offset + PAGE_SIZE)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
