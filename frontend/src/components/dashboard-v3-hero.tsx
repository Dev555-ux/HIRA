"use client";

import { ArrowRight, Check, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AiNetwork } from "@/components/dashboard-v2-hero";
import type { RosterEntry } from "@/components/dashboard-v2-hero";
import type { BriefHighlight } from "@/components/dashboard-hero";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { HealthScore } from "@/components/health-score";
import type { ActivityState } from "@/components/ui/activity-dot";
import { healthSignals } from "@/lib/analytics-insights";
import type { AnalyticsDashboard } from "@/lib/types";

function timeOfDayGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] || name;
}

// Dashboard V3's hero — Sprint 89 founder-polish pass. Still V1's glass
// shell (Card variant="hero") wrapping V2's live AI Network, but the network
// no longer sits in its own bordered/backdrop-blurred box (Sprint 88's
// "inner raised panel" read as a component dropped into the hero rather
// than part of it). It now shares the hero's own surface and ambient glow —
// one continuous premium surface, not a card nested in a card.
//
// The greeting stays on `type-display-xl` (a responsive 32px→56px clamp,
// tokened specifically "Home greeting") rather than the bigger fixed 72px
// `type-display-2xl` ("landing hero," full-bleed-width copy) — tried the
// larger token first, but at this column's real width (sharing the row
// with a 420px network) it wrapped the greeting across three lines, which
// reads as broken, not bold. The button row drops to exactly one loud
// action (`size="xl"`, the same landing-page-weight CTA token the
// marketing site's hero uses) plus two quiet icon/text-level utilities —
// Sprint 88's three same-weight buttons diluted which one mattered.
export function DashboardV3Hero({
  name,
  summary,
  highlights = [],
  needsAttention = false,
  isRefreshing,
  onRefresh,
  pendingCount = 0,
  roster,
  hubState = "success",
  healthData,
}: {
  name: string;
  summary: string;
  highlights?: BriefHighlight[];
  needsAttention?: boolean;
  isRefreshing: boolean;
  onRefresh: () => void;
  pendingCount?: number;
  roster: RosterEntry[];
  hubState?: ActivityState;
  healthData?: AnalyticsDashboard;
}) {
  const [greeting, setGreeting] = useState("Welcome back");
  useEffect(() => {
    setGreeting(timeOfDayGreeting());
  }, []);

  // Sprint 89 — on a fully healthy day, all six HealthScore pills read
  // "success" and say nothing the hero's own "Nothing urgent requires you"
  // line hasn't already said; six identical green pills is decoration, not
  // signal. Only surface the strip when it actually has something to flag.
  const hasHealthIssue = healthData ? healthSignals(healthData).some((s) => s.state !== "success") : false;

  return (
    <div className="mb-14 animate-fade-in-up">
      <Card
        variant="hero"
        className="relative min-h-[480px] overflow-hidden p-8 sm:p-10 lg:min-h-[560px] lg:p-14"
      >
        {/* Ambient glow field — three soft brand washes instead of two hard
            corner blooms, the center-right one sized and placed to sit
            directly behind the AI Network hub so the visualization reads as
            light emerging from the surface itself, not a separate object
            lit from outside. */}
        <div
          className="pointer-events-none absolute -left-20 -top-24 size-64 rounded-full bg-brand/[0.14] blur-3xl"
          aria-hidden="true"
        />
        <div
          className="pointer-events-none absolute right-[6%] top-1/2 size-[420px] -translate-y-1/2 rounded-full bg-brand/[0.16] blur-3xl"
          aria-hidden="true"
        />
        <div
          className="pointer-events-none absolute -bottom-28 -right-10 size-72 rounded-full bg-brand/10 blur-3xl"
          aria-hidden="true"
        />

        <div className="relative flex h-full flex-col gap-10 lg:flex-row lg:items-center lg:gap-8">
          <div className="min-w-0 flex-1">
            <h1 className="type-display-xl text-balance">
              {greeting}, {firstName(name)}
            </h1>

            <div className="mt-4">
              {highlights.length > 0 ? (
                <ul className="space-y-1.5">
                  {highlights.map((h) => (
                    <li key={h.label} className="flex items-center gap-2 text-base text-foreground/90">
                      <Check className="size-4 shrink-0 text-success" aria-hidden="true" />
                      {h.label}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-base text-muted-foreground">{summary}</p>
              )}
              {!needsAttention && (
                <p className="mt-1.5 text-base text-muted-foreground">Nothing urgent requires you.</p>
              )}
            </div>

            {healthData && hasHealthIssue && (
              <div className="mt-6">
                <HealthScore data={healthData} />
              </div>
            )}

            <div className="mt-9 flex flex-wrap items-center gap-x-5 gap-y-3">
              {pendingCount > 0 && (
                <Button asChild size="xl">
                  <Link href="/pending">
                    Review {pendingCount} {pendingCount === 1 ? "reply" : "replies"}
                    <ArrowRight />
                  </Link>
                </Button>
              )}
              <Button
                variant="ghost"
                size="icon"
                onClick={onRefresh}
                aria-label="Refresh"
                className="text-muted-foreground hover:text-foreground"
              >
                <RefreshCw className={isRefreshing ? "animate-spin" : ""} />
              </Button>
              <Link
                href="/demo"
                className="rounded-sm text-sm font-medium text-muted-foreground transition-colors duration-150 hover:text-foreground focus-visible:focus-ring"
              >
                Test AI →
              </Link>
            </div>
          </div>

          {/* The AI Network — full-size, unboxed, living directly on the
              hero surface. */}
          <div className="flex shrink-0 items-center justify-center lg:w-[420px]">
            <AiNetwork roster={roster} hubState={hubState} />
          </div>
        </div>
      </Card>
    </div>
  );
}
