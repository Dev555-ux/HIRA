"use client";

import { ArrowRight, Check, CheckCheck } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ReviewReplyCard } from "@/components/review-reply-card";
import { StatusPill } from "@/components/ui/status-pill";
import { WorkingIndicator } from "@/components/ui/working-indicator";
import type { ActivityState } from "@/components/ui/activity-dot";
import { cn } from "@/lib/utils";

// HIRA V5 — "Proof First": the hero demonstrates HIRA instead of describing
// it. Left column keeps the existing argument (headline/CTA); right column
// (dominant on desktop) plays one real HIRA workflow, once, event-driven —
// each stage advances only after the previous one's own hold elapses, using
// the same motion tokens those stages' CSS already animates with, not
// arbitrary numbers. Reuses ReviewReplyCard, WorkingIndicator, and
// StatusPill/ActivityDot verbatim rather than inventing parallel UI.
const CUSTOMER_MESSAGE = "Do you have availability for a cleaning this Thursday?";
const CUSTOMER_MESSAGE_TIME = "9:47 PM";
const DRAFTED_REPLY = "Thursday at 10:00 AM works — you're all set!";

const OUTCOME_ITEMS = ["Customer confirmed", "Appointment booked", "Calendar updated"];

const STAGES = ["idle", "message", "processing", "knowledge", "calendar", "draft", "resolved"] as const;
type Stage = (typeof STAGES)[number];

// One hold per transition (STAGES.length - 1), each reusing an existing
// motion token: --motion-fast (entrance stagger), --motion-narrative (reading
// time), --motion-ambient (one full working-line cycle), --motion-signature
// (a "system finished" beat, same token signature-demo uses for its settle).
const HOLDS_MS = [120, 1200, 1800, 700, 700, 1400] as const;

const DEMO_SUMMARY =
  `Live product demonstration: a customer messages at ${CUSTOMER_MESSAGE_TIME} asking, ` +
  `"${CUSTOMER_MESSAGE}" HIRA checks business knowledge and the calendar, then drafts a reply: ` +
  `"${DRAFTED_REPLY}" The business owner has nothing left to do — customer confirmed, appointment ` +
  `booked, calendar updated.`;

function useReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

function CustomerMessage() {
  return (
    <div className="animate-fade-in flex flex-col items-start gap-1">
      <div className="max-w-[85%] rounded-md bg-muted px-3 py-2 text-sm">{CUSTOMER_MESSAGE}</div>
      <span className="text-xs text-muted-foreground">{CUSTOMER_MESSAGE_TIME}</span>
    </div>
  );
}

function stepState(stageIndex: number, stepStage: Stage): ActivityState {
  const stepIndex = STAGES.indexOf(stepStage);
  if (stageIndex < stepIndex) return "idle";
  if (stageIndex === stepIndex) return "working";
  return "success";
}

function Outcome() {
  return (
    <div className="animate-signature-settle space-y-4 text-center">
      <p className="text-2xl font-bold tracking-tight sm:text-3xl">No action required</p>
      <ul className="space-y-1.5 text-left text-sm text-muted-foreground">
        {OUTCOME_ITEMS.map((item) => (
          <li key={item} className="flex items-center gap-2">
            <Check className="size-4 shrink-0 text-success" aria-hidden="true" />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ResolvedDemo() {
  return (
    <div className="space-y-4">
      <CustomerMessage />
      <div className="space-y-2">
        <StatusPill state="success">Using Business Knowledge</StatusPill>
        <StatusPill state="success">Calendar checked</StatusPill>
      </div>
      <Outcome />
    </div>
  );
}

function ProductDemo({
  reducedMotion,
  onResolved,
}: {
  reducedMotion: boolean;
  onResolved: () => void;
}) {
  const [stageIndex, setStageIndex] = useState(0);
  const stage = STAGES[stageIndex];

  // Event-driven, not timer-driven in spirit: each hold below IS the real
  // duration of the CSS animation that stage plays (working-line's own
  // --motion-ambient cycle, signature-settle's own --motion-signature), so a
  // stage only advances once its own animation has actually finished — not
  // an arbitrary schedule disconnected from what's on screen. Plays once;
  // once "resolved" is reached no further timer is scheduled.
  useEffect(() => {
    if (reducedMotion || stageIndex >= STAGES.length - 1) return;
    const timer = setTimeout(() => setStageIndex((i) => i + 1), HOLDS_MS[stageIndex]);
    return () => clearTimeout(timer);
  }, [stageIndex, reducedMotion]);

  useEffect(() => {
    if (stage === "resolved") onResolved();
  }, [stage, onResolved]);

  if (reducedMotion) {
    return (
      <Card role="img" aria-label={DEMO_SUMMARY} className="overflow-hidden p-5 sm:p-6">
        <div aria-hidden="true">
          <ResolvedDemo />
        </div>
      </Card>
    );
  }

  return (
    <Card
      role="group"
      aria-label={DEMO_SUMMARY}
      className="overflow-hidden p-5 sm:p-6"
    >
      <div aria-hidden="true" className="space-y-4">
        {stage !== "idle" && <CustomerMessage />}

        {stage === "processing" && (
          <WorkingIndicator state="working" label="HIRA is working" />
        )}

        {(stage === "knowledge" || stage === "calendar") && (
          <div className="space-y-2">
            <StatusPill state={stepState(stageIndex, "knowledge")}>
              Using Business Knowledge
            </StatusPill>
            <StatusPill state={stepState(stageIndex, "calendar")}>Calendar checked</StatusPill>
          </div>
        )}

        {stage === "draft" && (
          <ReviewReplyCard
            body={DRAFTED_REPLY}
            status="waiting"
            className="border-0 bg-transparent p-0 shadow-none"
          />
        )}

        {stage === "resolved" && <Outcome />}
      </div>
    </Card>
  );
}

export function Hero() {
  const reducedMotion = useReducedMotion();
  const [demoResolved, setDemoResolved] = useState(false);
  const resolved = reducedMotion || demoResolved;
  const handleResolved = useCallback(() => setDemoResolved(true), []);

  return (
    <section className="mx-auto flex max-w-6xl flex-col px-4 py-16 sm:px-6 sm:py-24 lg:grid lg:grid-cols-[1fr_1.15fr] lg:items-center lg:gap-12 lg:py-32">
      <div className="order-2 mt-12 text-center lg:order-1 lg:mt-0 lg:text-left">
        <div className="flex items-center justify-center gap-2.5 lg:justify-start">
          <span className="size-1.5 rounded-full bg-brand" aria-hidden="true" />
          <span className="text-[0.6875rem] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Founder Beta — limited early access
          </span>
        </div>

        <h1 className="mt-7 text-balance text-6xl font-black tracking-tighter sm:text-7xl lg:max-w-2xl xl:text-[5.25rem] 2xl:text-8xl">
          Never miss another{" "}
          <mark
            className={cn(
              "rounded-lg px-1.5 py-0.5 transition-colors duration-[var(--motion-signature)] ease-[var(--ease-out-quart)] [-webkit-box-decoration-break:clone] [box-decoration-break:clone]",
              resolved ? "bg-brand/15 text-brand" : "bg-muted text-foreground",
            )}
          >
            customer message
          </mark>
          .
        </h1>
        <p className="mt-6 max-w-md text-pretty text-lg text-muted-foreground sm:text-xl lg:mx-0 lg:max-w-sm">
          HIRA answers your customers on WhatsApp, books appointments, follows
          up on leads, and hands the conversation to your team the moment it
          needs a human touch.
        </p>
        <div className="mt-10 flex flex-col items-center gap-5 lg:items-start">
          <Button asChild size="xl">
            <Link href="/sign-up">
              Get started
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
          <a
            href="#how-it-works"
            className="text-sm font-medium text-foreground underline-offset-4 hover:underline"
          >
            See how it works
          </a>
        </div>
        <p className="mt-8 flex items-center justify-center gap-2 text-sm text-muted-foreground lg:justify-start">
          <CheckCheck className="size-4 shrink-0 text-success" aria-hidden="true" />
          Starts in Assisted Mode — you approve every reply until you trust it
        </p>
      </div>

      <div className="order-1 lg:order-2">
        <ProductDemo reducedMotion={reducedMotion} onResolved={handleResolved} />
      </div>
    </section>
  );
}
