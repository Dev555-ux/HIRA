"use client";

import { ArrowRight, Check, CheckCheck, Pause, Play } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ReviewReplyCard } from "@/components/review-reply-card";
import { StatusPill } from "@/components/ui/status-pill";
import { WorkingIndicator } from "@/components/ui/working-indicator";
import type { ActivityState } from "@/components/ui/activity-dot";
import { useInView } from "@/hooks/use-in-view";
import { cn } from "@/lib/utils";

// HIRA V5 — "Proof First": the hero demonstrates HIRA instead of describing
// it. Left column keeps the existing argument (headline/CTA); right column
// (dominant on desktop) plays one real HIRA workflow. Reuses ReviewReplyCard,
// WorkingIndicator, and StatusPill/ActivityDot verbatim rather than
// inventing parallel UI.
const CUSTOMER_MESSAGE = "Do you have availability for a cleaning this Thursday?";
const CUSTOMER_MESSAGE_TIME = "9:47 PM";
const DRAFTED_REPLY = "Thursday at 10:00 AM works — you're all set!";

const OUTCOME_ITEMS = ["Customer confirmed", "Appointment booked", "Calendar updated"];

const STAGES = ["idle", "message", "processing", "knowledge", "calendar", "draft", "resolved"] as const;
type Stage = (typeof STAGES)[number];

// V5.1: slowed down so each stage is actually readable, not just legible in
// a screenshot — deliberately paced rather than reused from the small
// --motion-* token scale (those top out at 1.8s; this is a narrative, not a
// micro-interaction), same reasoning signature-demo.tsx's own BEATS array
// already uses for its multi-second holds. One hold per transition
// (STAGES.length - 1): idle→message, message→processing, processing→
// knowledge, knowledge→calendar, calendar→draft, draft→resolved.
const HOLDS_MS = [400, 1800, 2600, 1600, 1600, 2400] as const;

// How long the resolved outcome stays on screen before the demo settles
// back to idle, ready to replay.
const RESOLVED_HOLD_MS = 6500;

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
  onReset,
}: {
  reducedMotion: boolean;
  onResolved: () => void;
  onReset: () => void;
}) {
  // Continuous (not "once") viewport tracking: every entry — the first one
  // on load, and every later re-entry after scrolling away — restarts the
  // story. Staying in view does NOT loop it; only a fresh entry does.
  const { ref: viewRef, inView } = useInView<HTMLDivElement>({ once: false, rootMargin: "0px" });
  const [stageIndex, setStageIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const stage = STAGES[stageIndex];

  useEffect(() => {
    if (reducedMotion || !inView) return;
    setStageIndex(0);
    setPlaying(true);
  }, [inView, reducedMotion]);

  // Advances one stage per hold while playing. Once "resolved" is reached,
  // holds there for RESOLVED_HOLD_MS, then settles back to idle and stops —
  // deliberately not a loop; only the inView effect above or a manual
  // Replay restarts it.
  useEffect(() => {
    if (!playing) return;
    if (stageIndex < STAGES.length - 1) {
      const timer = setTimeout(() => setStageIndex((i) => i + 1), HOLDS_MS[stageIndex]);
      return () => clearTimeout(timer);
    }
    const timer = setTimeout(() => {
      setStageIndex(0);
      setPlaying(false);
    }, RESOLVED_HOLD_MS);
    return () => clearTimeout(timer);
  }, [playing, stageIndex]);

  useEffect(() => {
    if (stage === "resolved") onResolved();
    if (stage === "idle") onReset();
  }, [stage, onResolved, onReset]);

  // Replay always restarts from stage 0; Resume continues playing from
  // wherever Pause froze it — distinct actions, not the same button always
  // restarting.
  const handleReplay = useCallback(() => {
    setStageIndex(0);
    setPlaying(true);
  }, []);
  const handleResume = useCallback(() => setPlaying(true), []);
  const handlePause = useCallback(() => setPlaying(false), []);
  const isPausedMidSequence = !playing && stageIndex > 0;
  const primaryAction = playing ? handlePause : isPausedMidSequence ? handleResume : handleReplay;
  const primaryLabel = playing ? "Pause demo" : isPausedMidSequence ? "Resume demo" : "Replay demo";

  if (reducedMotion) {
    return (
      <Card role="img" aria-label={DEMO_SUMMARY} className="overflow-hidden p-6 sm:p-8">
        <div aria-hidden="true">
          <ResolvedDemo />
        </div>
      </Card>
    );
  }

  return (
    <div ref={viewRef}>
      <Card
        role="group"
        aria-label={`${DEMO_SUMMARY} Use the button below to replay or pause.`}
        className="overflow-hidden p-6 sm:p-8"
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
              <StatusPill state={stepState(stageIndex, "calendar")}>
                Calendar checked
              </StatusPill>
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

        <div className="mt-4 flex justify-end">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={primaryAction}
            aria-label={primaryLabel}
          >
            {playing ? <Pause aria-hidden="true" /> : <Play aria-hidden="true" />}
          </Button>
        </div>
      </Card>
    </div>
  );
}

export function Hero() {
  const reducedMotion = useReducedMotion();
  const [demoResolved, setDemoResolved] = useState(false);
  const resolved = reducedMotion || demoResolved;
  const handleResolved = useCallback(() => setDemoResolved(true), []);
  const handleReset = useCallback(() => setDemoResolved(false), []);

  return (
    <section className="mx-auto flex max-w-6xl flex-col px-4 py-16 sm:px-6 sm:py-24 lg:grid lg:grid-cols-[0.9fr_1.25fr] lg:items-center lg:gap-12 lg:py-32">
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
        <ProductDemo reducedMotion={reducedMotion} onResolved={handleResolved} onReset={handleReset} />
      </div>
    </section>
  );
}
