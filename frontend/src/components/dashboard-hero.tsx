"use client";

import { ArrowRight, Check, MessageSquareText, RefreshCw, Sparkles } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DonutChart } from "@/components/ui/donut-chart";
import { HealthScore } from "@/components/health-score";
import type { AnalyticsAiImpact, AnalyticsDashboard } from "@/lib/types";

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

/** The dashboard's own hero — HIRA's "Business Snapshot" (Sprint 86, building
 * on the V6 "Morning Brief"): a greeting, then either a real "while you were
 * away" checklist (`highlights`, each one backed by a real today-scoped count
 * the caller already fetched) or, when there's nothing yet to report, the
 * plain one-sentence `summary` — never both, and never an invented highlight.
 * Closes with a calm "nothing urgent" line only when `needsAttention` is
 * false, so the brief never claims a clear day while the section right below
 * it is showing open work.
 *
 * Sprint 86 adds an optional right-side visual panel: a 30-day AI coverage
 * ring built from `aiImpact` (the same real AnalyticsAiImpact figures
 * Analytics already surfaces), deliberately labeled "Last 30 days" — never
 * blended into the strictly today-scoped `highlights` checklist, which would
 * quietly mix two different time windows into one list. Omitted entirely
 * (not shown zeroed) until there's real coverage to show.
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
  aiImpact,
  healthData,
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
  /** Sprint 86 — real 30-day AI impact figures (Home's fixed-range
   *  AnalyticsDashboard.ai_impact) driving the hero's coverage visual.
   *  Omitted (not passed) rather than zeroed until there's real coverage. */
  aiImpact?: AnalyticsAiImpact;
  /** Sprint 86A — the same analytics payload feeding the standalone Health
   *  Score strip, now folded into the hero itself so the "home screen of an
   *  AI COO" reads as one surface instead of a hero + a separate status row
   *  underneath it. Same HealthScore component/signals, just relocated. */
  healthData?: AnalyticsDashboard;
}) {
  const [greeting, setGreeting] = useState("Welcome back");

  useEffect(() => {
    setGreeting(timeOfDayGreeting());
  }, []);

  const totalCoverage = aiImpact ? aiImpact.conversations_handled + aiImpact.human_escalations : 0;
  const showVisual = Boolean(aiImpact) && totalCoverage > 0;

  return (
    <div className="mb-10 animate-fade-in-up">
      {/* Sprint 87 — the hero is now HIRA's one floating glass surface: a
          brand-tinted gradient wash + hairline brand border (Card
          variant="hero") with two soft ambient glows layered underneath the
          content, never touching the data itself. Everything that used to
          sit on the bare page background (greeting, highlights, health
          pills, actions, the AI coverage panel) now lives inside one
          premium surface instead of floating loose above a plain rect. */}
      <Card variant="hero" className="relative overflow-hidden p-6 sm:p-8 lg:p-10">
        <div
          className="pointer-events-none absolute -left-24 -top-32 size-72 rounded-full bg-brand/20 blur-3xl"
          aria-hidden="true"
        />
        <div
          className="pointer-events-none absolute -bottom-32 -right-16 size-80 rounded-full bg-brand/10 blur-3xl"
          aria-hidden="true"
        />
        <div className="relative flex flex-col gap-8 lg:flex-row lg:items-stretch lg:gap-10">
          <div className="min-w-0 flex-1">
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
            {healthData && (
              <div className="mt-5">
                <HealthScore data={healthData} />
              </div>
            )}
            <div className="mt-6 flex flex-wrap gap-2">
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

          {showVisual && aiImpact && (
            // The inner "raised" layer — a second, quieter surface nested
            // inside the outer glass hero (backdrop-blur over the gradient
            // wash showing through, not another opaque card) so the panel
            // reads as one layer deeper rather than a redundant second box.
            <div className="flex shrink-0 flex-col items-center justify-center gap-4 rounded-2xl border border-border/50 bg-background/60 px-10 py-8 shadow-e2 backdrop-blur-sm lg:w-[300px] dark:bg-background/40">
              <p className="type-caption text-center font-semibold uppercase tracking-wide text-muted-foreground">
                AI coverage · Last 30 days
              </p>
              <div className="relative flex items-center justify-center">
                {/* Sized to the chart's own circle (184px), not `inset-0`
                    against this wrapper — the wrapper also contains
                    DonutChart's "View as table" disclosure below the ring,
                    so `inset-0` stretched the glow into a tall oval that
                    swallowed the ring instead of haloing it. */}
                <div
                  className="absolute size-[184px] rounded-full bg-brand animate-ambient-pulse"
                  aria-hidden="true"
                />
                <DonutChart
                  title="AI coverage, last 30 days"
                  size={184}
                  showLegend={false}
                  segments={[
                    {
                      key: "handled",
                      label: "Handled by AI",
                      value: aiImpact.conversations_handled,
                      state: "success",
                    },
                    {
                      key: "escalated",
                      label: "Escalated to a human",
                      value: aiImpact.human_escalations,
                      state: "waiting",
                    },
                  ]}
                />
              </div>
              <div className="flex items-center gap-1.5 text-sm">
                <Sparkles className="size-3.5 text-brand" aria-hidden="true" />
                <span className="font-semibold">≈{aiImpact.estimated_hours_saved}h</span>
                <span className="text-muted-foreground">saved this month</span>
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
