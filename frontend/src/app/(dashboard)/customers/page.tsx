"use client";

import { AlertTriangle, RefreshCw, Search, Users } from "lucide-react";
import { useState } from "react";
import { CustomerDetailPane } from "@/components/customer-detail";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useCustomers } from "@/hooks/use-customers";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import type { Customer } from "@/lib/types";
import { cn, formatRelativeTime } from "@/lib/utils";

const PAGE_SIZE = 20;

const STAGE_LABEL: Record<string, string> = {
  new: "New",
  contacted: "Contacted",
  qualified: "Qualified",
  proposal_sent: "Proposal sent",
  negotiation: "Negotiation",
  won: "Won",
  lost: "Lost",
};

export default function CustomersPage() {
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const debouncedQuery = useDebouncedValue(query);

  const { data, isLoading, isError, error, isFetching, refetch } = useCustomers({
    search: debouncedQuery || undefined,
    limit: PAGE_SIZE,
    offset,
  });
  const customers = data?.data ?? [];
  const total = data?.meta.total ?? 0;

  function handleSearchChange(value: string) {
    setQuery(value);
    setOffset(0);
  }

  return (
    <>
      <PageHeader
        title="Customers"
        description="People who have messaged your business."
        action={
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className={isFetching ? "animate-spin" : ""} />
            Refresh
          </Button>
        }
      />

      <div className="relative mb-4 max-w-sm">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Search customers…"
          value={query}
          onChange={(e) => handleSearchChange(e.target.value)}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <CustomerList
          customers={customers}
          isLoading={isLoading}
          isError={isError}
          error={error}
          onRetry={refetch}
          selectedId={selectedId}
          onSelect={setSelectedId}
          hasQuery={query.length > 0}
          total={total}
          offset={offset}
          onOffsetChange={setOffset}
        />
        <CustomerDetailPane customerId={selectedId} onBack={() => setSelectedId(null)} />
      </div>
    </>
  );
}

function CustomerList({
  customers,
  isLoading,
  isError,
  error,
  onRetry,
  selectedId,
  onSelect,
  hasQuery,
  total,
  offset,
  onOffsetChange,
}: {
  customers: Customer[];
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  onRetry: () => void;
  selectedId: string | null;
  onSelect: (id: string) => void;
  hasQuery: boolean;
  total: number;
  offset: number;
  onOffsetChange: (offset: number) => void;
}) {
  return (
    <Card
      className={cn("flex min-h-[420px] flex-col", selectedId !== null ? "hidden lg:flex" : "flex")}
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
            title="Couldn't load customers"
            description={error instanceof Error ? error.message : "Something went wrong."}
            action={
              <Button size="sm" onClick={onRetry}>
                Retry
              </Button>
            }
            className="border-0 py-16"
          />
        )}

        {!isLoading && !isError && customers.length === 0 && (
          <EmptyState
            icon={Users}
            title={hasQuery ? "No matches" : "No customers yet"}
            description={
              hasQuery
                ? "Try a different search term."
                : "Everyone who has messaged your business will show up here."
            }
            className="border-0 py-16"
          />
        )}

        {!isLoading && !isError && customers.length > 0 && (
          <ul className="divide-y">
            {customers.map((customer) => (
              <li key={customer.id}>
                <button
                  type="button"
                  onClick={() => onSelect(customer.id)}
                  className={cn(
                    "flex w-full flex-col gap-1 px-4 py-3 text-left transition-colors hover:bg-accent/50",
                    selectedId === customer.id && "bg-accent",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium">
                      {customer.display_name || customer.wa_phone}
                    </span>
                    {customer.last_message_at && (
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {formatRelativeTime(customer.last_message_at)}
                      </span>
                    )}
                  </div>
                  <p className="truncate text-xs text-muted-foreground">
                    {customer.conversation_count} conversation
                    {customer.conversation_count === 1 ? "" : "s"}
                  </p>
                  {customer.lead && (
                    <Badge variant="secondary" className="w-fit">
                      {STAGE_LABEL[customer.lead.stage] ?? customer.lead.stage}
                    </Badge>
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
