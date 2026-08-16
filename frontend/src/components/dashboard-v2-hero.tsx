"use client";

import { ArrowRight, Check, MessageSquareText, RefreshCw } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { roleLabel } from "@/components/ai-metrics-section";
import { Button } from "@/components/ui/button";
import { AIAvatar } from "@/components/ui/ai-avatar";
import type { ActivityState } from "@/components/ui/activity-dot";
import { HealthScore } from "@/components/health-score";
import type { AnalyticsDashboard } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface V2Highlight {
  icon: LucideIcon;
  label: string;
}

export interface RosterEntry {
  role: string;
  count: number;
  pct: number;
  mostActive: boolean;
  /** Sprint 88 — real 30-day turn count > 0. `roster` now always lists
   *  every real employee role (see the page's own comment); this is what
   *  tells the network/roster views which ones to draw bright vs. dim. */
  active: boolean;
}

function timeOfDayGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] || name;
}

// Evenly spaced positions around the hub on a 0-100 viewBox, starting at
// the top and going clockwise — the same "radial cluster scales by
// container width alone" trick as the marketing site's orchestration hub
// (components/marketing/signature-demo.tsx), generalized to N (a dynamic
// roster length) instead of a fixed 4.
function radialPosition(index: number, total: number, radius = 36): { x: number; y: number } {
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2;
  return { x: 50 + radius * Math.cos(angle), y: 50 + radius * Math.sin(angle) };
}

// The hero's live visualization — HIRA (the hub) connected to every real AI
// employee role (`roster`, computed by the page as the full, fixed 4-role
// set from ROLE_LABEL, each flagged `active` from ai_performance.employee_
// utilisation). Spoke opacity/width scale with real share of total turns
// for active roles; idle roles (Sprint 88 dogfooding finding — hiding them
// made a 2-of-4-active team read as a 2-node line, and made the other two
// real employees look like they didn't exist) render as a dim, static grey
// spoke instead of being omitted — the role is real even when idle, only
// its activity is zero. Ambient, not narrative: every active connection
// pulses continuously (the existing `animate-signature-pulse` keyframe as a
// permanent "alive" signal, not a scripted sequence) — the honest read of
// 30-day aggregate data, since there's no real live "who's working right
// now" signal to show.
export function AiNetwork({ roster, hubState }: { roster: RosterEntry[]; hubState: ActivityState }) {
  const anyActive = roster.some((r) => r.active);

  if (!anyActive) {
    return (
      <div className="flex h-full min-h-[280px] flex-col items-center justify-center gap-2 text-center">
        <div className="opacity-40">
          <AIAvatar name="HIRA" size="xl" />
        </div>
        <p className="max-w-[220px] text-sm text-muted-foreground">
          HIRA is warming up — this view comes alive once your AI team starts handling conversations.
        </p>
      </div>
    );
  }

  return (
    <div
      className="relative mx-auto aspect-square w-full max-w-[360px]"
      role="img"
      aria-label={roster
        .map((r) =>
          r.active
            ? `${roleLabel(r.role)}: ${r.count} turns, ${r.pct}% of activity`
            : `${roleLabel(r.role)}: no activity in the last 30 days`,
        )
        .join(". ")}
    >
      <svg viewBox="0 0 100 100" className="absolute inset-0 h-full w-full" aria-hidden="true">
        {roster.map((r, i) => {
          const pos = radialPosition(i, roster.length);
          if (!r.active) {
            return (
              <line
                key={r.role}
                x1={50}
                y1={50}
                x2={pos.x}
                y2={pos.y}
                vectorEffect="non-scaling-stroke"
                strokeWidth={1}
                strokeDasharray="2 3"
                className="stroke-border"
              />
            );
          }
          const strength = Math.max(0.25, r.pct / 100);
          return (
            <g key={r.role}>
              <line
                x1={50}
                y1={50}
                x2={pos.x}
                y2={pos.y}
                vectorEffect="non-scaling-stroke"
                strokeWidth={1}
                className="stroke-brand/15"
              />
              <line
                x1={50}
                y1={50}
                x2={pos.x}
                y2={pos.y}
                pathLength={100}
                vectorEffect="non-scaling-stroke"
                strokeWidth={0.75 + strength}
                strokeDasharray="6 94"
                className="stroke-brand animate-signature-pulse"
                style={{ opacity: 0.35 + strength * 0.5 }}
              />
            </g>
          );
        })}
      </svg>

      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
        <div className="animate-ambient-pulse absolute inset-0 -m-3 rounded-full bg-brand/25" aria-hidden="true" />
        <AIAvatar name="HIRA" size="xl" state={hubState} className="relative" />
      </div>

      {roster.map((r, i) => {
        const pos = radialPosition(i, roster.length);
        return (
          <div
            key={r.role}
            className={cn(
              "absolute flex w-24 -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-1.5 text-center",
              !r.active && "opacity-40",
            )}
            style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
          >
            <AIAvatar name={roleLabel(r.role)} size="lg" state={r.active ? (r.mostActive ? "success" : "idle") : "idle"} />
            <span className="text-[11px] font-medium text-foreground">{roleLabel(r.role)}</span>
            <span className="text-[10px] text-muted-foreground">{r.active ? `${r.count} turns` : "No activity"}</span>
          </div>
        );
      })}
    </div>
  );
}

/** Dashboard V2's Business Snapshot hero — a from-scratch visual language
 *  (not `Card variant="hero"`, deliberately: V2 is asked to forget V1's
 *  hero recipe entirely, not reskin it) built from the same design tokens.
 *  Two zones: the greeting/highlights/health/actions column, and the real
 *  AI-network visualization built from `roster` (see AiNetwork above). */
export function DashboardV2Hero({
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
  highlights?: V2Highlight[];
  needsAttention?: boolean;
  isRefreshing: boolean;
  onRefresh: () => void;
  pendingCount?: number;
  roster: RosterEntry[];
  /** Sprint 88 — ties the hub avatar's status dot to real business_health
   *  alerts (computed by the page) instead of a hardcoded "success". */
  hubState?: ActivityState;
  healthData?: AnalyticsDashboard;
}) {
  const [greeting, setGreeting] = useState("Welcome back");
  useEffect(() => {
    setGreeting(timeOfDayGreeting());
  }, []);

  return (
    <div
      className={cn(
        "relative mb-10 min-h-[460px] overflow-hidden rounded-[2rem] p-8 sm:p-10 lg:min-h-[520px] lg:p-14",
        "bg-[linear-gradient(135deg,var(--card)_0%,var(--card)_55%,color-mix(in_oklab,var(--brand)_7%,var(--card))_100%)]",
        "shadow-e4",
        "animate-fade-in-up",
      )}
    >
      <div
        className="pointer-events-none absolute -right-32 top-1/2 size-[420px] -translate-y-1/2 rounded-full bg-brand/10 blur-3xl"
        aria-hidden="true"
      />
      <div className="relative flex h-full flex-col gap-10 lg:flex-row lg:items-center">
        <div className="flex min-w-0 flex-1 flex-col justify-center">
          <h1 className="type-display-xl text-balance">
            {greeting}, {firstName(name)}
          </h1>
          {highlights.length > 0 ? (
            <ul className="mt-5 space-y-2">
              {highlights.map((h) => (
                <li key={h.label} className="flex items-center gap-2.5 text-base">
                  <Check className="size-4 shrink-0 text-success" aria-hidden="true" />
                  {h.label}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-5 text-base text-muted-foreground">{summary}</p>
          )}
          {!needsAttention && (
            <p className="mt-3 text-base text-muted-foreground">Nothing urgent requires you.</p>
          )}
          {healthData && (
            <div className="mt-6">
              <HealthScore data={healthData} />
            </div>
          )}
          <div className="mt-8 flex flex-wrap gap-2">
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

        <div className="flex shrink-0 items-center justify-center lg:w-[380px]">
          <AiNetwork roster={roster} hubState={hubState} />
        </div>
      </div>
    </div>
  );
}
