"use client";

import { BookOpen, Search, Upload } from "lucide-react";
import { useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function KnowledgeBasePage() {
  const [query, setQuery] = useState("");

  return (
    <>
      <PageHeader
        title="Knowledge Base"
        description="Facts your AI receptionist uses to answer customers."
        action={
          <Button size="sm" disabled title="Upload endpoint coming soon">
            <Upload /> Upload document
          </Button>
        }
      />

      <div className="relative mb-4 max-w-sm">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Search knowledge base…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="grid grid-cols-[1fr_120px_120px] gap-4 border-b px-5 py-3 text-xs font-medium text-muted-foreground">
            <span>Title</span>
            <span>Chunks</span>
            <span>Embedding</span>
          </div>
          <EmptyState
            icon={BookOpen}
            title="No knowledge entries yet"
            description="Add FAQs and business facts here. Entries are chunked and embedded locally for semantic search."
            className="border-0"
          />
        </CardContent>
      </Card>
    </>
  );
}
