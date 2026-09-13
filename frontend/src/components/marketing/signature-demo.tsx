"use client";

import { BookOpen, Calendar, UserCheck, Users } from "lucide-react";
import { useEffect, useState } from "react";
import type { LucideIcon } from "lucide-react";
import { PhoneFrame } from "@/components/marketing/phone-frame";
import { AIAvatar } from "@/components/ui/ai-avatar";
import { Badge } from "@/components/ui/badge";
import { useInView } from "@/hooks/use-in-view";
import { useReducedMotion } from "@/hooks/use-reduced-motion";
import { cn } from "@/lib/utils";

// V5.1 "Orchestration Hub": rebuilt from a sparse six-node row into a
// radial layout — HIRA (the hub, center) actively coordinating four
// connected systems, not four unrelated lights turning on in a line. Same
// customer scenario as the hero (§ hero.tsx) rather than the old BMW
// dealership example, so the landing page reads as one continuous story
// instead of two unrelated demos. One coordinate system (a 0–100 viewBox
// doubling as percentage positions) replaces the old wide/compact dual
// layout — a radial cluster scales by container width alone, so no
// separate mobile coordinate set is needed anymore.
type SystemId = "knowledge" | "calendar" | "team" | "crm";
type SystemStatus = "idle" | "active" | "done";

const HUB = { x: 50, y: 50 };

const SYSTEMS: {
  id: SystemId;
  label: string;
  icon: LucideIcon;
  workingText: string;
  doneText: string;
  x: number;
  y: number;
}[] = [
  { id: "knowledge", label: "Knowledge", icon: BookOpen, workingText: "Searching…", doneText: "Verified", x: 50, y: 12 },
  { id: "calendar", label: "Calendar", icon: Calendar, workingText: "Checking availability…", doneText: "Thu · 10:00 AM", x: 86, y: 50 },
  { id: "team", label: "Team", icon: UserCheck, workingText: "Notifying…", doneText: "Team notified", x: 50, y: 88 },
  { id: "crm", label: "CRM", icon: Users, workingText: "Finding customer…", doneText: "Customer found", x: 14, y: 50 },
];

const IDLE_STATUS: Record<SystemId, SystemStatus> = {
  knowledge: "idle",
  calendar: "idle",
  team: "idle",
  crm: "idle",
};

const DONE_STATUS: Record<SystemId, SystemStatus> = {
  knowledge: "done",
  calendar: "done",
  team: "done",
  crm: "done",
};

type Beat = {
  hold: number;
  message?: boolean;
  systems?: Partial<Record<SystemId, SystemStatus>>;
  settled?: boolean;
  reply?: boolean;
  closing?: boolean;
};

// Sprint 66 PR-2 — data model only, no engine change: BEATS (a single
// hardcoded sequence) becomes SCENARIOS (a named sequence per scenario).
// DemoWidget still walks whichever `beats` array it's given exactly as
// before; only where that array comes from changed. Only "cleaning" is
// wired up to render today (DEFAULT_SCENARIO_ID below) — the other three
// are real, valid data, ready for the scenario-selector UI (a later PR),
// not yet reachable from anywhere.
export type ScenarioId = "cleaning" | "dental" | "pricing" | "escalation";

export type Scenario = {
  id: ScenarioId;
  chipLabel: string;
  customerMessage: string;
  replyMessage: string;
  beats: Beat[];
};

// Same "overlap, not a rigid queue" philosophy as before, sized to four
// systems: Knowledge and CRM run together, then Calendar and Team. This is
// verbatim the old top-level BEATS constant, now SCENARIOS.cleaning.beats.
const CLEANING_BEATS: Beat[] = [
  { hold: 1400 }, // Scene 1 — idle, quiet, nothing moves
  { hold: 500, message: true }, // Scene 2 — the message arrives
  { hold: 300 }, // a breath before HIRA reacts
  { hold: 700, systems: { knowledge: "active" } },
  { hold: 300, systems: { crm: "active" } },
  { hold: 500, systems: { knowledge: "done" } },
  { hold: 200, systems: { calendar: "active" } },
  { hold: 400, systems: { crm: "done" } },
  { hold: 300, systems: { team: "active" } },
  { hold: 700, systems: { calendar: "done" } },
  { hold: 400, systems: { team: "done" } },
  { hold: 700, settled: true }, // Scene 5 — the signature moment: HIRA settles, then a quiet pause
  { hold: 2200, reply: true }, // Scene 6 — the reply
  { hold: 3200, closing: true }, // Scene 7 — "One message. Four business systems. Zero manual work."
  { hold: 600 }, // hold before the loop resets
];

// Same four-system rhythm as cleaning — a clinic booking is structurally
// the same flow, only the copy changes.
const DENTAL_BEATS: Beat[] = CLEANING_BEATS;

// Only two systems answer a pricing question — Knowledge and CRM run
// together, then settle. Calendar/Team simply never receive a beat and
// stay idle throughout; SystemNode already renders that correctly.
const PRICING_BEATS: Beat[] = [
  { hold: 1400 },
  { hold: 500, message: true },
  { hold: 300 },
  { hold: 700, systems: { knowledge: "active" } },
  { hold: 500, systems: { crm: "active" } },
  { hold: 700, systems: { knowledge: "done" } },
  { hold: 500, systems: { crm: "done" } },
  { hold: 700, settled: true },
  { hold: 2200, reply: true },
  { hold: 3200, closing: true },
  { hold: 600 },
];

// An escalation only needs CRM (to pull up the customer) and Team (to hand
// off) — Knowledge/Calendar stay idle throughout.
const ESCALATION_BEATS: Beat[] = [
  { hold: 1400 },
  { hold: 500, message: true },
  { hold: 300 },
  { hold: 700, systems: { crm: "active" } },
  { hold: 500, systems: { team: "active" } },
  { hold: 700, systems: { crm: "done" } },
  { hold: 500, systems: { team: "done" } },
  { hold: 700, settled: true },
  { hold: 2200, reply: true },
  { hold: 3200, closing: true },
  { hold: 600 },
];

export const SCENARIOS: Record<ScenarioId, Scenario> = {
  cleaning: {
    id: "cleaning",
    chipLabel: "Cleaning",
    customerMessage: "Do you have availability for a cleaning this Thursday?",
    replyMessage: "Thursday at 10:00 AM works — you're all set!",
    beats: CLEANING_BEATS,
  },
  dental: {
    id: "dental",
    chipLabel: "Dental",
    customerMessage: "Can I book a consultation with Dr. Martinez tomorrow afternoon?",
    replyMessage: "Dr. Martinez has an opening tomorrow at 3:30 PM — you're all set!",
    beats: DENTAL_BEATS,
  },
  pricing: {
    id: "pricing",
    chipLabel: "Pricing",
    customerMessage: "What do your plans include, and is there human escalation?",
    replyMessage:
      "Every plan includes human escalation, grounded in what you've told HIRA — no generic guessing.",
    beats: PRICING_BEATS,
  },
  escalation: {
    id: "escalation",
    chipLabel: "Escalation",
    customerMessage: "I need to speak with your team about an urgent issue.",
    replyMessage: "I've flagged this to your team with the full conversation — they'll take it from here.",
    beats: ESCALATION_BEATS,
  },
};

// Default to today's scenario — what SignatureDemo's ScenarioSelector
// (below) opens on.
export const DEFAULT_SCENARIO_ID: ScenarioId = "cleaning";

// Cables radiate from the hub outward — HIRA reaching into each system,
// not systems reporting in independently. Same two-line technique as
// before (a dim continuous base + a bright travelling dash on top) so the
// connection itself never flickers, only the pulse riding on it.
function Cables({ status }: { status: Record<SystemId, SystemStatus> }) {
  return (
    <svg viewBox="0 0 100 100" className="absolute inset-0 h-full w-full" aria-hidden="true">
      {SYSTEMS.map((sys) => {
        const state = status[sys.id];

        // Signal & Depth PR-5 — previously null: the very first frame (and
        // every idle system before its own beat fires) showed a floating
        // icon with no visible relationship to the hub at all. A faint,
        // static baseline (no animation, matching the same near-invisible
        // treatment idle gets everywhere else in this file) shows the
        // topology at rest — "these four are connected to HIRA" reads
        // before a single beat has run, exactly what the graph should
        // communicate before anyone reads the copy.
        if (state === "idle") {
          return (
            <line
              key={sys.id}
              x1={HUB.x}
              y1={HUB.y}
              x2={sys.x}
              y2={sys.y}
              vectorEffect="non-scaling-stroke"
              strokeWidth={1}
              className="stroke-border/40"
            />
          );
        }

        if (state === "active") {
          return (
            <g key={sys.id}>
              <line x1={HUB.x} y1={HUB.y} x2={sys.x} y2={sys.y} vectorEffect="non-scaling-stroke" strokeWidth={1} className="stroke-primary/25" />
              <line
                x1={HUB.x}
                y1={HUB.y}
                x2={sys.x}
                y2={sys.y}
                pathLength={100}
                vectorEffect="non-scaling-stroke"
                strokeWidth={1}
                strokeDasharray="8 92"
                className="stroke-primary animate-signature-pulse"
              />
            </g>
          );
        }

        // Only "done" reaches here now (idle and active both returned
        // above). No transition class: this renders as a *different*
        // element than the active <g> above (same key, different tag), so
        // React unmounts/remounts rather than restyles in place — a
        // transition here would never fire.
        //
        // Signal & Depth PR-4 — this used to render the identical neutral
        // stroke-border an untouched cable would use, so a completed
        // connection carried no visual credit at all once its pulse
        // animation finished. Tinting it with the same success color
        // SystemNode already uses for its own done state ties the two
        // together — "this connection succeeded," not just "this line
        // exists." (PR-5 gave idle its own faint line above, distinct from
        // both this and the untouched-null case that no longer exists.)
        return (
          <line
            key={sys.id}
            x1={HUB.x}
            y1={HUB.y}
            x2={sys.x}
            y2={sys.y}
            vectorEffect="non-scaling-stroke"
            strokeWidth={1}
            className="stroke-success/35"
          />
        );
      })}
    </svg>
  );
}

function SystemNode({
  sys,
  status,
  settled,
  statusTextVisible,
}: {
  sys: (typeof SYSTEMS)[number];
  status: SystemStatus;
  settled: boolean;
  statusTextVisible: boolean;
}) {
  const Icon = sys.icon;
  const statusText = status === "active" ? sys.workingText : status === "done" ? `→ ${sys.doneText}` : "";
  const showStatus = status !== "idle" && statusTextVisible;

  return (
    <div
      className="absolute flex w-24 -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-1.5 text-center"
      style={{ left: `${sys.x}%`, top: `${sys.y}%` }}
    >
      <span
        className={cn(
          "flex size-8 items-center justify-center rounded-full border bg-card transition-all duration-[var(--motion-slow)] [&_svg]:size-4",
          status === "idle" && "border-border/50 text-muted-foreground/40",
          status === "active" && "scale-110 border-primary bg-primary/10 text-primary",
          status === "done" && !settled && "border-success bg-success/10 text-success",
          status === "done" && settled && "border-foreground/40 bg-foreground/5 text-muted-foreground",
        )}
      >
        <Icon aria-hidden="true" />
      </span>
      <span
        className={cn(
          "text-[11px] font-medium uppercase tracking-wide transition-colors duration-[var(--motion-slow)]",
          status === "idle" ? "text-muted-foreground/35" : "text-muted-foreground",
        )}
      >
        {sys.label}
      </span>
      <span
        className={cn(
          "block text-[10px] leading-tight transition-opacity duration-[var(--motion-slow)]",
          showStatus ? "opacity-100" : "opacity-0",
          status === "done" ? "text-success" : "text-muted-foreground/70",
        )}
      >
        {statusText}
      </span>
    </div>
  );
}

// Signal & Depth PR-4 — rounded-md read as a generic chat bubble, not a
// real one. hero.tsx's own ProductDemo already established the tail-corner
// shape (rounded-2xl, tightened on the corner nearest the sender) for this
// exact page's other conversation UI — matching it here is conversation
// realism AND principle 5's "one motif, echoed" rather than two different
// bubble languages on the same page.
function CustomerBubble({ text }: { text: string }) {
  return (
    <div className="animate-fade-in flex justify-start">
      <div className="max-w-[85%] rounded-2xl rounded-bl-md bg-muted px-3 py-2 text-sm">{text}</div>
    </div>
  );
}

function ReplyBubble({ text }: { text: string }) {
  return (
    <div className="animate-fade-in flex justify-end">
      <div className="max-w-[85%] rounded-2xl rounded-br-md bg-secondary px-3 py-2 text-sm text-secondary-foreground">
        {text}
      </div>
    </div>
  );
}

function ClosingLine() {
  return (
    <div className="animate-fade-in absolute inset-0 flex flex-col items-center justify-center gap-3 bg-background px-6 text-center">
      <p className="text-sm text-muted-foreground">One message. Four business systems. Zero manual work.</p>
      <p className="text-2xl font-semibold tracking-tight">This is HIRA.</p>
    </div>
  );
}

// Cinematic rebuild — the three class strings the animated and
// reduced-motion branches both render into, hoisted so the two can never
// drift apart. The stage stacks on phones and goes side-by-side at lg,
// which is also where the hero's own 460px copy rail engages.
const STAGE_LAYOUT =
  "flex w-full flex-col items-center gap-10 lg:min-h-[580px] lg:flex-row lg:items-center lg:justify-center lg:gap-8";
const PHONE_COLUMN = "w-full max-w-[280px] shrink-0 lg:max-w-[284px]";
// min-h keeps the phone a constant height across every beat — without it
// the frame grows as the reply arrives and the whole stage jumps. Bubbles
// sit at the bottom, the way a real conversation fills a screen upward.
const PHONE_SCREEN = "relative flex min-h-[300px] flex-col justify-end gap-3";
const CANVAS_COLUMN = "relative aspect-square w-full max-w-[340px] shrink-0 sm:max-w-[380px] lg:max-w-[480px]";

// Sprint 66 PR-3 — `key={scenarioId}` at the call site (see Hero, which
// owns the selector) remounts this whole widget on scenario change: every
// useState here reinitializes to its default and every effect's cleanup
// runs before the new instance's effects fire. That's the entire
// reset-and-restart mechanism — no manual "reset on scenario change"
// effect needed, no risk of a stale timer reading the new scenario's
// (possibly shorter) beats array. The engine below is otherwise
// byte-for-byte what PR-2 shipped.
export function OrchestrationStage({ scenarioId }: { scenarioId: ScenarioId }) {
  const reducedMotion = useReducedMotion();
  // DESIGN-MOTION-001 §7.3: at rest until scrolled into view, then alive;
  // pauses again if scrolled away.
  const { ref: viewRef, inView } = useInView<HTMLDivElement>({ once: false, rootMargin: "0px" });
  const scenario = SCENARIOS[scenarioId];
  const [beatIndex, setBeatIndex] = useState(0);
  const [messageVisible, setMessageVisible] = useState(false);
  const [status, setStatus] = useState<Record<SystemId, SystemStatus>>(IDLE_STATUS);
  const [settled, setSettled] = useState(false);
  const [replyVisible, setReplyVisible] = useState(false);
  const [closingVisible, setClosingVisible] = useState(false);
  const [paused, setPaused] = useState(false);
  const [tabHidden, setTabHidden] = useState(false);

  useEffect(() => {
    const onVisibility = () => setTabHidden(document.hidden);
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  useEffect(() => {
    if (paused || tabHidden || reducedMotion || !inView) return;
    const timer = setTimeout(() => {
      const nextIndex = beatIndex + 1;
      if (nextIndex >= scenario.beats.length) {
        setMessageVisible(false);
        setStatus(IDLE_STATUS);
        setSettled(false);
        setReplyVisible(false);
        setClosingVisible(false);
        setBeatIndex(0);
        return;
      }
      const beat = scenario.beats[nextIndex];
      if (beat.message) setMessageVisible(true);
      if (beat.systems) setStatus((prev) => ({ ...prev, ...beat.systems }));
      if (beat.settled) setSettled(true);
      if (beat.reply) setReplyVisible(true);
      if (beat.closing) setClosingVisible(true);
      setBeatIndex(nextIndex);
    }, scenario.beats[beatIndex].hold);
    return () => clearTimeout(timer);
  }, [beatIndex, paused, tabHidden, reducedMotion, inView, scenario]);

  const anyActive = Object.values(status).some((s) => s === "active");
  const hubState = settled ? "success" : anyActive ? "working" : "idle";

  const summary =
    `Demo: a customer messages HIRA asking, "${scenario.customerMessage}" HIRA coordinates four ` +
    "connected systems — Knowledge, CRM, Calendar, and Team — each working independently before " +
    `settling together in one synchronized moment and sending a reply: "${scenario.replyMessage}" One ` +
    "message, four systems, zero manual work.";

  if (reducedMotion) {
    return (
      <div role="img" aria-label={summary} className={STAGE_LAYOUT}>
        <div aria-hidden="true" className={PHONE_COLUMN}>
          <PhoneFrame>
            <div className={PHONE_SCREEN}>
              <CustomerBubble text={scenario.customerMessage} />
              <ReplyBubble text={scenario.replyMessage} />
            </div>
          </PhoneFrame>
        </div>
        <div aria-hidden="true" className={CANVAS_COLUMN}>
          <Cables status={DONE_STATUS} />
          {/* Same static hub glow as the animated branch below, at its
              "success" end state — the reduced-motion render is a
              single resolved frame, so this needs no transition here. */}
          <div className="absolute left-1/2 top-1/2 isolate -translate-x-1/2 -translate-y-1/2">
            <div aria-hidden="true" className="absolute left-1/2 top-1/2 -z-10 size-20 -translate-x-1/2 -translate-y-1/2 rounded-full bg-success/15 blur-xl" />
            {/* Same elevated dais as the animated branch below. */}
            <div className="rounded-2xl bg-card p-1.5 shadow-e2 ring-1 ring-border/50">
              <AIAvatar name="HIRA" size="xl" state="success" />
            </div>
          </div>
          {SYSTEMS.map((sys) => (
            <SystemNode key={sys.id} sys={sys} status="done" settled statusTextVisible />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div
      ref={viewRef}
      role="group"
      aria-label={`${summary} Animation pauses while hovered or focused.`}
      tabIndex={0}
      className={cn(
        STAGE_LAYOUT,
        "rounded-2xl outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
      )}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      {/* Cinematic rebuild — the conversation and the orchestration graph
          were previously stacked inside one narrow Card (bubble, graph,
          reply), which is what kept the graph boxed at 280–320px. The
          reference hero stages them side by side: the phone plays the
          conversation, the network runs beside it at full size. Same
          engine, same beats, same `status` object driving both halves —
          only the arrangement changed. */}
      <div aria-hidden="true" className={PHONE_COLUMN}>
        <PhoneFrame>
          <div className={PHONE_SCREEN}>
            {messageVisible && !closingVisible && <CustomerBubble text={scenario.customerMessage} />}
            {replyVisible && !closingVisible && <ReplyBubble text={scenario.replyMessage} />}
            {closingVisible && <ClosingLine />}
          </div>
        </PhoneFrame>
      </div>

      <div aria-hidden="true" className={CANVAS_COLUMN}>
        <Cables status={status} />
          {/* Signal & Depth PR-4 — HIRA Core prominence: a tight, static
              glow directly behind the hub, distinct from AtmosphereBackground's
              much larger ambient blur behind the whole phone. Colored by the
              same `hubState` already computed above for AIAvatar's own state
              prop — no new state, just reusing the existing derived value —
              so the glow itself becomes another (very quiet) instance of
              principle 1: it only carries color once something is actually
              happening. `isolate` matters here: this wrapper is `absolute`
              with no z-index of its own, so without it the child's `-z-10`
              would escape to the *aspect-square canvas's* stacking context
              and paint behind the SVG cables too, not just behind the
              avatar — the same class of bug final-cta.tsx's isolate fix
              addressed earlier this sprint.
              Signal & Depth PR-5 — the avatar alone (56px, same size as
              before) wasn't visually distinct enough from the satellite
              icons in kind, only in size. A dais (a card-elevated plate
              around it, shadow-e2) gives the hub its own layer of depth the
              satellites don't have — "the brain sits above the board," not
              just "the brain is a bigger dot." AIAvatar itself is
              untouched; this is a wrapper, not a modification to the
              shared component. */}
          <div
            className={cn(
              "absolute left-1/2 top-1/2 isolate -translate-x-1/2 -translate-y-1/2",
              settled && "animate-signature-settle",
            )}
          >
            <div
              aria-hidden="true"
              className={cn(
                "absolute left-1/2 top-1/2 -z-10 size-20 -translate-x-1/2 -translate-y-1/2 rounded-full blur-xl transition-colors duration-[var(--motion-slow)]",
                hubState === "success"
                  ? "bg-success/15"
                  : hubState === "working"
                    ? "bg-primary/10"
                    : "bg-transparent",
              )}
            />
            <div className="rounded-2xl bg-card p-1.5 shadow-e2 ring-1 ring-border/50">
              <AIAvatar name="HIRA" size="xl" state={hubState} />
            </div>
          </div>
        {SYSTEMS.map((sys) => (
          <SystemNode
            key={sys.id}
            sys={sys}
            status={status[sys.id]}
            settled={settled}
            statusTextVisible={!settled}
          />
        ))}
      </div>
    </div>
  );
}

// Sprint 66 PR-3 — the four scenarios in the order the ticket lists them,
// and their chip emoji. Not part of the Scenario data model itself
// (SCENARIOS stays presentation-agnostic) — this is UI-layer data, so it
// lives next to the component that's the only thing that reads it.
const SCENARIO_ORDER: ScenarioId[] = ["cleaning", "dental", "pricing", "escalation"];
const SCENARIO_EMOJI: Record<ScenarioId, string> = {
  cleaning: "🧹",
  dental: "🦷",
  pricing: "💰",
  escalation: "🚨",
};

// Native <input type="radio"> chips, not a hand-rolled role="radiogroup":
// a real radio group gets correct roving-tabindex, arrow-key navigation,
// and Home/End behavior from the browser for free — re-implementing that
// in JS is exactly the kind of thing a native element already does better.
// <fieldset>/<legend> gives assistive tech the group's accessible name
// without a redundant visible heading. Reuses Badge (the app's existing
// pill/chip primitive, already on --motion-fast) instead of hand-styling
// a new chip — its focus-visible ring matches the ring already used on the
// demo widget itself below.
export function ScenarioSelector({
  scenarioId,
  onChange,
  className,
}: {
  scenarioId: ScenarioId;
  onChange: (id: ScenarioId) => void;
  className?: string;
}) {
  return (
    <fieldset className={cn("flex flex-wrap justify-center gap-2", className)}>
      <legend className="sr-only">Choose a demo scenario</legend>
      {SCENARIO_ORDER.map((id) => (
        <label key={id} className="cursor-pointer">
          <input
            type="radio"
            name="signature-demo-scenario"
            value={id}
            checked={scenarioId === id}
            onChange={() => onChange(id)}
            className="peer sr-only"
          />
          <Badge
            variant={scenarioId === id ? "default" : "outline"}
            className={cn(
              "gap-1.5 px-3 py-1 text-sm peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-background",
              // Signal & Depth PR-7 — unselected chips had no hover feedback
              // at all beyond the label's own cursor:pointer, unlike every
              // other clickable control in this app (Button, Card
              // interactive both pair hover with a visible state change).
              // Reuses Button's own outline-variant hover language
              // (hover:bg-accent hover:text-accent-foreground) rather than
              // inventing a new one. The selected chip is left alone — it's
              // already the active state, nothing new to hint at on hover.
              scenarioId !== id && "hover:bg-accent hover:text-accent-foreground",
            )}
          >
            <span aria-hidden="true">{SCENARIO_EMOJI[id]}</span>
            {SCENARIOS[id].chipLabel}
          </Badge>
        </label>
      ))}
    </fieldset>
  );
}

// Cinematic rebuild — the standalone SignatureDemo <section> and its own
// atmosphere layer are both gone. The demo is no longer a thing you scroll
// to below the fold; it *is* the hero's right-hand stage, and the hero owns
// the single atmosphere layer for the whole opening screen. What used to
// live here (selector + phone + graph) is now exported piecewise above and
// composed by hero.tsx.
