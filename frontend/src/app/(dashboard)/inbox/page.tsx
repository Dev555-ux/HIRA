"use client";

import { Inbox as InboxIcon, Search } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const FILTERS = ["All", "Pending", "Escalated", "Closed"] as const;
const NOT_CONNECTED_HINT = "Search and filters will be available once the inbox is connected.";

export default function InboxPage() {
  return (
    <>
      <PageHeader
        title="Inbox"
        description="Customer conversations from WhatsApp."
      />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search conversations…"
            disabled
            title={NOT_CONNECTED_HINT}
          />
        </div>
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <Button
              key={f}
              size="sm"
              variant={f === "All" ? "secondary" : "ghost"}
              disabled
              title={NOT_CONNECTED_HINT}
            >
              {f}
            </Button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <Card className="min-h-[420px]">
          <CardContent className="p-0">
            <div className="flex h-full items-center justify-center p-6">
              <EmptyState
                icon={InboxIcon}
                title="Inbox is coming soon"
                description="You'll be able to see every customer conversation here, in one place."
                className="border-0"
              />
            </div>
          </CardContent>
        </Card>
        <Card className="min-h-[420px]">
          <CardContent className="flex h-full items-center justify-center p-6">
            <div className="text-center text-sm text-muted-foreground">
              <Badge variant="secondary" className="mb-3">
                Message timeline
              </Badge>
              <p>Conversation threads will appear here once the inbox is available.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
