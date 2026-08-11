"use client";

import { ArrowRight, Check, MessageSquareText, RefreshCw } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

export interface BriefHighlight {
  icon: LucideIcon;
  label: string;
}

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

/** The dashboard's own hero — HIRA V6 "Morning Brief": a greeting, then
 * either a real "while you were away" checklist (`highlights`, each one
 * backed by a real today-scoped count the caller already fetched) or, when
 * there's nothing yet to report, the plain one-sentence `summary` — never
 * both, and never an invented highlight. Closes with a calm "nothing urgent"
 * line only when `needsAttention` is false, so the brief never claims a
 * clear day while the section right below it is showing open work.
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
  highlights = [],
  needsAttention = false,
  isRefreshing,
  onRefresh,
  pendingCount = 0,
}: {
  name: string;
  summary: string;
  /** Real, today-scoped "what HIRA did" lines — omit an item entirely
   *  rather than show a zero count; empty array falls back to `summary`. */
  highlights?: BriefHighlight[];
  /** True when "Needs your attention" below has real open items — suppresses
   *  the brief's own "nothing urgent" line so the two never disagree. */
  needsAttention?: boolean;
  isRefreshing: boolean;
  onRefresh: () => void;
  /** When > 0, promotes a "Review N replies" primary CTA ahead of the
   *  existing actions (DESIGN-SCREENBOOK-002 §4). Optional/defaulted so
   *  every existing caller and test is unaffected. */
  pendingCount?: number;
}) {
  const [greeting, setGreeting] = useState("Welcome back");

  useEffect(() => {
    setGreeting(timeOfDayGreeting());
  }, []);

  return (
    <div className="mb-8 flex flex-col gap-6 animate-fade-in-up sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="type-display-xl text-balance">
          {greeting}, {firstName(name)}
        </h1>
        {highlights.length > 0 ? (
          <>
            <p className="mt-3 text-base text-muted-foreground">While you were away…</p>
            <ul className="mt-3 space-y-1.5">
              {highlights.map((h) => (
                <li key={h.label} className="flex items-center gap-2 text-base">
                  <Check className="size-4 shrink-0 text-success" aria-hidden="true" />
                  {h.label}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="mt-2 text-base text-muted-foreground">{summary}</p>
        )}
        {!needsAttention && (
          <p className="mt-3 text-base text-muted-foreground">Nothing urgent requires you.</p>
        )}
      </div>
      <div className="flex shrink-0 flex-wrap gap-2">
        {pendingCount > 0 && (
          <Button asChild size="sm">
            <Link href="/pending">
              Review {pendingCount} {pendingCount === 1 ? "reply" : "replies"}
              <ArrowRight />
            </Link>
          </Button>
        )}
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
