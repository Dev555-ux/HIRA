"use client";

import { ArrowRight, Check, CheckCheck, Pause, Play, UserRoundCheck } from "lucide-react";
import Link from "next/link";
import { AnimatePresence, motion, MotionConfig } from "framer-motion";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { StatusPill } from "@/components/ui/status-pill";
import { ThinkingIndicator } from "@/components/ui/working-indicator";
import { useInView } from "@/hooks/use-in-view";
import { useReducedMotion } from "@/hooks/use-reduced-motion";
import { cn } from "@/lib/utils";

// HIRA V6.1 — "Premium Proof, quieter": same one-real-workflow thesis as V6,
// restaged twice more per founder review — (1) the reasoning now narrates in
// full (thinking → checking the calendar → verifying → replying →
// reserving), and (2) the card itself recedes (lighter border/glow/shadow,
// quieter chips) so the headline stays the primary thing a visitor reads.
// Still reuses StatusPill and ThinkingIndicator verbatim from the app's own
// AI-state vocabulary (DESIGN-MOTION-001 §6) rather than a chat-app
// typing-dots cliché.
const CUSTOMER_MESSAGE = "Hi, can you book an AC service tomorrow after 3 PM?";
const CUSTOMER_MESSAGE_TIME = "9:47 PM";
// Rendered as separate lines in one bubble — a real business reply reads as
// short, scannable sentences, not one run-on paragraph.
const HIRA_REPLY_LINES = [
  "You're all set!",
  "I've booked your service for tomorrow at 4:00 PM.",
  "I've assigned Ravi to your service.",
  "You'll receive a reminder one hour before your appointment.",
];
const HIRA_REPLY_TIME = "9:48 PM";

const VERIFY_CHECKS = ["Calendar checked", "Service area verified", "Technician assigned"];
const RESERVED_CHECK = "Appointment confirmed";

const STAGES = [
  "idle",
  "message",
  "thinking",
  "checking",
  "verified",
  "reply",
  "reserved",
  "resolved",
] as const;
type Stage = (typeof STAGES)[number];

// The working line's label narrates what HIRA is doing at each thinking
// beat — "thinking" and "checking" are the same primitive, just a different
// sentence, so the story reads as one continuous train of thought.
const THINKING_LABEL: Partial<Record<Stage, string>> = {
  thinking: "Thinking…",
  checking: "Checking technician availability…",
};

// One hold per transition (STAGES.length - 1). Paced to be read, not just
// glanced at: idle→message, message→thinking, thinking→checking,
// checking→verified, verified→reply, reply→reserved, reserved→resolved.
const HOLDS_MS = [600, 1300, 1900, 1500, 1700, 1400, 2000] as const;

// How long the resolved outcome stays on screen before the demo settles
// back to idle, ready to replay.
const RESOLVED_HOLD_MS = 5500;

const DEMO_SUMMARY =
  `Live product demonstration: a customer messages at ${CUSTOMER_MESSAGE_TIME} asking, ` +
  `"${CUSTOMER_MESSAGE}" HIRA checks technician availability, the calendar, and the service ` +
  `area, assigns a technician, then replies: "${HIRA_REPLY_LINES.join(" ")}" Appointment ` +
  `confirmed — nothing left for the owner to do, and HIRA only escalates if it ever needs a human.`;

// The house entrance curve (--ease-out-quart) as a bezier framer-motion can
// consume directly, for the handful of non-spring transitions below.
const EASE_OUT = [0.16, 1, 0.3, 1] as const;

// A touch slower and floatier than a snappy UI spring — this is a narrative
// beat arriving, not a control responding to a click.
const springIn = { type: "spring", stiffness: 130, damping: 20, mass: 0.7 } as const;

const staggerContainer = {
  hidden: {},
  show: { transition: { staggerChildren: 0.12, delayChildren: 0.08 } },
};

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: springIn },
};

// A quieter chip for inside the demo card: keeps the ActivityDot's success
// colour (still a real state signal) but drops StatusPill's own border/
// shadow so it doesn't compete with the conversation for attention.
// text-foreground/70 (not text-muted-foreground) — WCAG AA audit found the
// muted-on-muted pairing measured 4.4:1 against the card, just under the
// 4.5:1 floor for this text size; this passes with real margin (~6.7:1)
// while staying visually quieter than full-strength foreground.
const quietPillClassName = "border-transparent bg-muted/60 text-foreground/70 shadow-none";

function ChipsRow({ items }: { items: string[] }) {
  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="show"
      className="flex flex-wrap gap-2"
    >
      {items.map((label) => (
        <motion.div key={label} variants={fadeUp}>
          <StatusPill state="success" className={quietPillClassName}>
            {label}
          </StatusPill>
        </motion.div>
      ))}
    </motion.div>
  );
}

function CustomerBubble() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ ...springIn, delay: 0.1 }}
      className="flex flex-col items-start gap-1"
    >
      <div className="max-w-[82%] rounded-2xl rounded-bl-md bg-muted px-3.5 py-2.5 text-sm">
        {CUSTOMER_MESSAGE}
      </div>
      <span className="text-[0.6875rem] text-muted-foreground">{CUSTOMER_MESSAGE_TIME}</span>
    </motion.div>
  );
}

function HiraBubble({ typing, sent }: { typing: boolean; sent: boolean }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ ...springIn, delay: 0.08 }}
      className="flex flex-col items-end gap-1 self-end"
    >
      {/* text-foreground, not the paired text-brand-foreground token — WCAG
          AA audit measured that pairing at 3.2:1 on this bg, under the 4.5:1
          floor for text-sm. Dark text on the brand fill passes at ~5.7:1. */}
      <div className="max-w-[78%] space-y-1 rounded-2xl rounded-br-md bg-brand px-3.5 py-2.5 text-sm text-foreground">
        {HIRA_REPLY_LINES.map((line, i) => (
          <p key={line}>
            {line}
            {typing && i === HIRA_REPLY_LINES.length - 1 && (
              <motion.span
                aria-hidden="true"
                animate={{ opacity: [1, 0] }}
                transition={{ duration: 0.8, repeat: Infinity, repeatType: "reverse" }}
                className="ml-0.5 inline-block h-3.5 w-[2px] translate-y-0.5 bg-brand-foreground align-middle"
              />
            )}
          </p>
        ))}
      </div>
      {sent && (
        <motion.span
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3, duration: 0.3 }}
          className="flex items-center gap-1 text-[0.6875rem] text-muted-foreground"
        >
          {HIRA_REPLY_TIME}
          <CheckCheck className="size-3 text-[#53bdeb]" aria-hidden="true" />
        </motion.span>
      )}
    </motion.div>
  );
}

function ResolvedBanner() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={springIn}
      className="relative flex items-center gap-3 overflow-hidden rounded-xl bg-success/10 px-4 py-3"
    >
      {/* A single light sweep on arrival — never loops, just marks the
          moment as a small, one-time celebration rather than decoration. */}
      <motion.span
        aria-hidden="true"
        initial={{ x: "-120%" }}
        animate={{ x: "220%" }}
        transition={{ duration: 1, ease: EASE_OUT, delay: 0.35 }}
        className="pointer-events-none absolute inset-y-0 left-0 w-1/3 -skew-x-12 bg-gradient-to-r from-transparent via-white/40 to-transparent"
      />
      <motion.span
        initial={{ scale: 0.5, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ ...springIn, delay: 0.1 }}
        className="flex size-7 shrink-0 items-center justify-center rounded-full bg-success text-success-foreground"
      >
        <Check className="size-4" aria-hidden="true" />
      </motion.span>
      <div>
        <p className="text-sm font-semibold">Reminder scheduled</p>
        <p className="text-xs text-muted-foreground">No action needed — it&apos;s handled.</p>
      </div>
    </motion.div>
  );
}

function ConversationBody({ stage }: { stage: Stage }) {
  const showVerified = stage === "verified" || stage === "reply" || stage === "reserved" || stage === "resolved";
  const showReply = stage === "reply" || stage === "reserved" || stage === "resolved";
  const showReserved = stage === "reserved" || stage === "resolved";

  return (
    <div className="flex flex-col gap-3.5">
      {stage !== "idle" && <CustomerBubble />}

      <AnimatePresence>
        {THINKING_LABEL[stage] && (
          <motion.div
            key={stage}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25, ease: EASE_OUT }}
            className="mt-1"
          >
            <ThinkingIndicator label={THINKING_LABEL[stage]} className="w-40" />
          </motion.div>
        )}
      </AnimatePresence>

      {showVerified && (
        <div className="mt-1">
          <ChipsRow items={VERIFY_CHECKS} />
        </div>
      )}

      {showReply && <HiraBubble typing={stage === "reply"} sent={showReserved} />}

      {showReserved && (
        <div className="mt-1">
          <ChipsRow items={[RESERVED_CHECK]} />
        </div>
      )}

      <AnimatePresence>
        {stage === "resolved" && (
          <div className="mt-1.5">
            <ResolvedBanner key="resolved" />
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

function CardHeader() {
  return (
    <div className="flex items-center gap-2 border-b border-border/50 pb-3">
      <span className="relative flex size-2">
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-success/50" />
        <span className="relative inline-flex size-2 rounded-full bg-success" />
      </span>
      <span className="text-xs font-medium text-muted-foreground">Business WhatsApp</span>
    </div>
  );
}

function GlassCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-[32px] bg-gradient-to-br from-brand/20 via-border/30 to-transparent p-px shadow-e3">
      <div className="min-h-[23rem] rounded-[32px] bg-card/90 p-6 backdrop-blur-backdrop-lg sm:p-8">
        {children}
      </div>
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
      <GlassCard>
        <div role="img" aria-label={DEMO_SUMMARY}>
          <CardHeader />
          <div className="mt-4">
            <ConversationBody stage="resolved" />
          </div>
        </div>
      </GlassCard>
    );
  }

  return (
    <div ref={viewRef}>
      <GlassCard>
        <div
          role="group"
          aria-label={`${DEMO_SUMMARY} Use the button below to replay or pause.`}
        >
          <div className="flex items-center justify-between">
            <CardHeader />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={primaryAction}
              aria-label={primaryLabel}
              className="-mr-2 -mt-1"
            >
              {playing ? <Pause aria-hidden="true" /> : <Play aria-hidden="true" />}
            </Button>
          </div>
          <div className="mt-4" aria-hidden="true">
            <ConversationBody stage={stage} />
          </div>
        </div>
      </GlassCard>
    </div>
  );
}

// Sprint 66 PR-5 — was FloatingDemo: continuous mouse-tracking parallax
// (useMotionValue/useSpring), an infinite y:[0,-4,0] float, and an infinite
// animate-ambient-pulse glow. All three are exactly what this pass removes
// — DESIGN-MOTION-001 §7.2 already says "no parallax on the hero," and a
// second animated glow here would make two atmosphere layers (the section
// now has its own, see HeroAtmosphere) instead of one. What's left is the
// one-time entrance (fade + rise + scale, springIn) — a single composed
// arrival, not a loop — so the anchor object still feels alive on first
// paint without ever repeating. ProductDemo itself (the actual proof
// animation: stages, holds, bubbles) is untouched below.
function ComposedDemo({ reducedMotion, ...props }: React.ComponentProps<typeof ProductDemo>) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ ...springIn, delay: 0.2 }}
      // Signal & Depth PR-1 — max-w-md capped the card well short of the
      // wider lg:col-span-7 track above, so the grid change alone only
      // repositioned it, it didn't grow it. lg:max-w-lg lets it actually
      // fill more of its new column. GlassCard/ProductDemo's internal
      // measurements are all relative (percentage bubble widths, min-h),
      // so they scale with this instead of overflowing.
      className="mx-auto max-w-md lg:mx-0 lg:max-w-lg"
    >
      <ProductDemo reducedMotion={reducedMotion} {...props} />
      <p className="mt-4 flex items-center justify-center gap-1.5 text-center text-xs text-muted-foreground">
        <UserRoundCheck className="size-3.5 shrink-0" aria-hidden="true" />
        Escalates only when human attention is required
      </p>
    </motion.div>
  );
}

// Sprint 66 PR-5 — the one atmosphere layer the ticket asks for: a static,
// aria-hidden radial glow behind the whole section. No keyframes, no
// scroll/mouse coupling, so "respect reduced motion" holds by having
// nothing to reduce. pointer-events-none keeps it fully inert. Pure CSS —
// no image asset, so nothing here can affect LCP.
//
// Sprint 66 PR-10 — opacity 0.07 -> 0.02, a real bug this glow introduced:
// a production Lighthouse run flagged the "Founder Beta" eyebrow text
// (text-muted-foreground) at 4.27:1 against this glow's warm-tinted
// background, under the 4.5:1 AA floor — confirmed by rebuilding at
// bg-brand/0 (glow fully off), where the same audit passes clean, so this
// glow is entirely why that background isn't plain --background anymore.
// 0.05 (4.37:1) and 0.03 (4.46:1) still fell short; 0.02 passes (verified
// by rebuilding and re-running Lighthouse at each step, not calculated).
function HeroAtmosphere() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      <div className="absolute left-1/2 top-0 h-[42rem] w-[64rem] -translate-x-1/2 -translate-y-1/3 rounded-full bg-brand/[0.02] blur-3xl" />
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
    <MotionConfig reducedMotion={reducedMotion ? "always" : "never"}>
      {/* Signal & Depth PR-1 — grid-cols-[1fr_1.05fr] gave the copy column
          and the demo near-equal weight (~49/51). Principle 6 ("space
          allocation is a hierarchy signal"): the demo is the proof, so it
          gets the larger share — a 5/7 split, not a coin-flip. Below lg
          this is still a plain flex column; nothing here changes below
          that breakpoint. */}
      <section className="relative mx-auto flex max-w-7xl flex-col px-4 py-20 sm:px-6 sm:py-28 lg:grid lg:grid-cols-12 lg:items-center lg:gap-20 lg:py-40 xl:gap-24">
        <HeroAtmosphere />
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          animate="show"
          className="mt-12 text-center lg:order-1 lg:col-span-5 lg:mt-0 lg:text-left"
        >
          <motion.div
            variants={fadeUp}
            className="flex items-center justify-center gap-2.5 lg:justify-start"
          >
            <span className="size-1.5 rounded-full bg-brand" aria-hidden="true" />
            <span className="text-[0.6875rem] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Founder Beta — limited early access
            </span>
          </motion.div>

          <motion.h1
            variants={fadeUp}
            className="mt-9 text-balance text-5xl font-black leading-tight tracking-tighter sm:text-6xl lg:max-w-xl xl:text-7xl"
          >
            Never miss another customer{" "}
            {/* Signal & Depth PR-2 — one deliberate accent word, not a
                two-word block: "customer message" as a single highlighted
                span read as a highlighted phrase, not a precise signal.
                "message" alone is the one word the whole product turns on —
                the thing that arrives, gets answered, and (via `resolved`)
                is the one word that lights up brand-colored the moment the
                demo actually finishes answering it. Still the same
                state-tied mechanism, just naming a single word instead of
                two.
                text-foreground (not text-brand) on the resolved wash — WCAG
                AA audit measured brand-on-brand/15 at ~2.8:1, under the 3:1
                floor for large text even at this size. Foreground on the
                same tint passes at ~15:1; the tint alone still carries the
                "resolved" signal. */}
            <mark
              className={cn(
                "rounded-lg px-1.5 py-0.5 transition-colors duration-[var(--motion-signature)] ease-[var(--ease-out-quart)] [-webkit-box-decoration-break:clone] [box-decoration-break:clone]",
                resolved ? "bg-brand/15 text-foreground" : "bg-muted text-foreground",
              )}
            >
              message
            </mark>
            .
          </motion.h1>
          <motion.p
            variants={fadeUp}
            className="mx-auto mt-8 max-w-[52ch] text-pretty text-lg leading-relaxed text-muted-foreground sm:text-xl lg:mx-0"
          >
            HIRA answers your customers on WhatsApp, books appointments, follows
            up on leads, and hands the conversation to your team the moment it
            needs a human touch.
          </motion.p>
          <motion.div
            variants={fadeUp}
            className="mt-12 flex flex-col items-center gap-6 lg:items-start"
          >
            <motion.div
              whileHover={{ y: -2, scale: 1.01 }}
              whileTap={{ y: 0, scale: 0.99 }}
              transition={{ type: "spring", stiffness: 300, damping: 24 }}
              className="inline-block"
            >
              <Button asChild size="xl">
                <Link href="/sign-up">
                  Get started
                  <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
            </motion.div>
            <a
              href="#how-it-works"
              className="text-sm font-medium text-foreground underline-offset-4 hover:underline"
            >
              See how it works
            </a>
          </motion.div>
          <motion.p
            variants={fadeUp}
            className="mt-10 flex items-center justify-center gap-2 text-sm text-muted-foreground lg:justify-start"
          >
            <CheckCheck className="size-4 shrink-0 text-success" aria-hidden="true" />
            Starts in Assisted Mode — you approve every reply until you trust it
          </motion.p>
        </motion.div>

        <div className="lg:order-2 lg:col-span-7">
          <ComposedDemo reducedMotion={reducedMotion} onResolved={handleResolved} onReset={handleReset} />
        </div>
      </section>
    </MotionConfig>
  );
}
