"use client";

import { Search, Users } from "lucide-react";
import { useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function CustomersPage() {
  const [query, setQuery] = useState("");

  return (
    <>
      <PageHeader title="Customers" description="People who have messaged your business." />

      <div className="relative mb-4 max-w-sm">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Search customers…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="grid grid-cols-4 gap-4 border-b px-5 py-3 text-xs font-medium text-muted-foreground">
            <span>Name</span>
            <span>Phone</span>
            <span>Conversations</span>
            <span>Last message</span>
          </div>
          <EmptyState
            icon={Users}
            title="No customers yet"
            description="Customers appear here once the customers API is connected."
            className="border-0"
          />
        </CardContent>
      </Card>
    </>
  );
}
