"use client";

import { MessageSquareText, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

function timeOfDayGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

// First token only — "Good afternoon, Jordan A. Whitfield-Smith" reads like a
// mail-merge, not a greeting a person would actually say.
function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] || name;
}

/** The dashboard's own hero — replaces the generic PageHeader used by every
 * other page with a greeting, a one-sentence real-data summary (computed by
 * the caller, since it owns the KPI queries), and the two actions an owner
 * reaches for first. Kept to two short lines of text plus a button row —
 * deliberately not a full-bleed banner.
 *
 * The greeting starts as "Welcome back" and only switches to a time-of-day
 * greeting after mount (an effect, not the initial render) — this page is
 * statically prerendered, so computing "Good afternoon" vs "Good evening"
 * during the render itself would embed whatever hour the build happened to
 * run at into the HTML, then mismatch every visitor's actual local clock on
 * hydration. Deferring to an effect keeps server and first-paint markup
 * identical and only personalizes after hydration completes.
 *
 * `animate-fade-in-up` plays once, on mount, and is not reapplied on
 * subsequent renders (refetches change props, not the element identity) —
 * a single settle-in moment, not a repeating flourish. */
export function DashboardHero({
  name,
  summary,
  isRefreshing,
  onRefresh,
}: {
  name: string;
  summary: string;
  isRefreshing: boolean;
  onRefresh: () => void;
}) {
  const [greeting, setGreeting] = useState("Welcome back");

  useEffect(() => {
    setGreeting(timeOfDayGreeting());
  }, []);

  return (
    <div className="mb-8 flex flex-col gap-4 animate-fade-in-up sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          {greeting}, {firstName(name)}
        </h1>
        <p className="mt-1.5 text-sm text-muted-foreground">{summary}</p>
      </div>
      <div className="flex shrink-0 gap-2">
        <Button variant="outline" size="sm" onClick={onRefresh}>
          <RefreshCw className={isRefreshing ? "animate-spin" : ""} />
          Refresh
        </Button>
        <Button asChild size="sm" variant="outline">
          <Link href="/demo">
            <MessageSquareText />
            Test AI
          </Link>
        </Button>
      </div>
    </div>
  );
}
