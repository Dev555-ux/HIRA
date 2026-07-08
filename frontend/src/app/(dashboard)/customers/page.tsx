"use client";

import { Search, Users } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function CustomersPage() {
  return (
    <>
      <PageHeader title="Customers" description="People who have messaged your business." />

      <div className="relative mb-4 max-w-sm">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Search customers…"
          disabled
          title="Search will be available once the customer list is connected."
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
            title="Customer list is coming soon"
            description="Everyone who has messaged your business will show up here."
            className="border-0"
          />
        </CardContent>
      </Card>
    </>
  );
}
