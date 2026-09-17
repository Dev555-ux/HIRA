"use client";

import { BookOpen, Calendar, UserCheck, Users } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { LucideIcon } from "lucide-react";
import { PhoneFrame } from "@/components/marketing/phone-frame";
import {
  ChatHeader,
  ClosingLine,
  DeviceShell,
  Composer,
  CustomerBubble,
  DateDivider,
  FlowGraph,
  ReplyBubble,
  SystemRow,
  TypingBubble,
} from "@/components/marketing/stage-parts";
import { Badge } from "@/components/ui/badge";
import { useInView } from "motion/react";
import { useReducedMotion } from "@/hooks/use-reduced-motion";
import { cn } from "@/lib/utils";

// This file is the stage's ENGINE — scenarios, beats, the timer, and the
// derived state they produce. How that state looks lives in stage-parts.tsx.
// The split is deliberate: PR-2 rebuilt the entire presentation and left the
// timing untouched, and keeping them apart is what makes that auditable.
//
// V5.1 "Orchestration Hub" staged HIRA as a radial cross — four systems on
// the compass points of a square canvas. PR-2 replaced it with a left-to-
// right flow (see FlowGraph): the cross gave every system equal visual
// weight in a layout with no direction, so the diagram never said which way
// the work travelled, and its 11px labels could not carry a description. The
// scenario data and beat timings below are unchanged.
type SystemId = "knowledge" | "calendar" | "team" | "crm";
type SystemStatus = "idle" | "active" | "done";

// PR-2 — `role` is new; x/y are gone. The coordinates described the radial
// cross layout this PR replaces (see FlowGraph below), and nothing computes
// positions from data any more.
//
// `role` exists because the graph had no resting state worth reading: before
// a beat fires, every node showed an icon and a 11px label and nothing else,
// so "what is this diagram telling me" took a full animation cycle to
// answer. A standing one-line role answers it in the first frame, which is
// the actual brief — understand the orchestration in two seconds.
//
// The strings are HIRA's own, narrowed from copy already on this page rather
// than taken from the reference: "Escalates to a human" is the Trust strip's
// own "Escalates to humans"; the other three are the indicative form of the
// workingText each system already had ("Checking availability…" →  "Checks
// real availability"). No new claims, no new capabilities implied.
const SYSTEMS: {
  id: SystemId;
  label: string;
  role: string;
  icon: LucideIcon;
  workingText: string;
  doneText: string;
}[] = [
  { id: "crm", label: "CRM", role: "Finds the customer record", icon: Users, workingText: "Finding customer…", doneText: "Customer found" },
  { id: "knowledge", label: "Knowledge", role: "Searches your knowledge base", icon: BookOpen, workingText: "Searching…", doneText: "Verified" },
  { id: "calendar", label: "Calendar", role: "Checks real availability", icon: Calendar, workingText: "Checking availability…", doneText: "Thu · 10:00 AM" },
  { id: "team", label: "Team", role: "Escalates to a human", icon: UserCheck, workingText: "Notifying…", doneText: "Team notified" },
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

// PR-3 — two flags added (`followUp`, `confirm`), nothing else about the
// beat model changed. The thread was two messages, which cannot fill a phone
// screen no matter how the device is proportioned; the sparseness was a
// content problem wearing a layout problem's clothes.
type Beat = {
  hold: number;
  message?: boolean;
  systems?: Partial<Record<SystemId, SystemStatus>>;
  settled?: boolean;
  reply?: boolean;
  followUp?: boolean;
  confirm?: boolean;
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
  // PR-3 — the closing exchange. Every real booking ends with the customer
  // acknowledging and the business confirming the follow-through, and its
  // absence was most of why the screen read as a mockup. The confirmations
  // restate capabilities the page already claims (Calendar books, HIRA
  // reminds) rather than introducing new ones.
  followUpMessage: string;
  confirmMessage: string;
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
  { hold: 1600, reply: true }, // Scene 6 — the reply
  { hold: 1300, followUp: true }, // Scene 7 — the customer acknowledges
  { hold: 2400, confirm: true }, // Scene 8 — HIRA confirms the follow-through
  { hold: 3200, closing: true }, // Scene 9 — "One message. Four business systems. Zero manual work."
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
  { hold: 1600, reply: true },
  { hold: 1300, followUp: true },
  { hold: 2400, confirm: true },
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
  { hold: 1600, reply: true },
  { hold: 1300, followUp: true },
  { hold: 2400, confirm: true },
  { hold: 3200, closing: true },
  { hold: 600 },
];

export const SCENARIOS: Record<ScenarioId, Scenario> = {
  cleaning: {
    id: "cleaning",
    chipLabel: "Cleaning",
    customerMessage: "Do you have availability for a cleaning this Thursday?",
    replyMessage: "Thursday at 10:00 AM works — you're all set!",
    followUpMessage: "Perfect, thank you!",
    confirmMessage: "Calendar invite sent. I'll remind you an hour before.",
    beats: CLEANING_BEATS,
  },
  dental: {
    id: "dental",
    chipLabel: "Dental",
    customerMessage: "Can I book a consultation with Dr. Martinez tomorrow afternoon?",
    replyMessage: "Dr. Martinez has an opening tomorrow at 3:30 PM — you're all set!",
    followUpMessage: "That works, thanks!",
    confirmMessage: "Booked. I'll send a reminder the morning of.",
    beats: DENTAL_BEATS,
  },
  pricing: {
    id: "pricing",
    chipLabel: "Pricing",
    customerMessage: "What do your plans include, and is there human escalation?",
    replyMessage:
      "Every plan includes human escalation, grounded in what you've told HIRA — no generic guessing.",
    followUpMessage: "Can someone walk me through it?",
    confirmMessage: "Of course — I've asked the team to reach out today.",
    beats: PRICING_BEATS,
  },
  escalation: {
    id: "escalation",
    chipLabel: "Escalation",
    customerMessage: "I need to speak with your team about an urgent issue.",
    replyMessage: "I've flagged this to your team with the full conversation — they'll take it from here.",
    followUpMessage: "Thank you, that's a relief.",
    confirmMessage: "They've seen it and someone is picking it up now.",
    beats: ESCALATION_BEATS,
  },
};

// Default to today's scenario — what SignatureDemo's ScenarioSelector
// (below) opens on.
export const DEFAULT_SCENARIO_ID: ScenarioId = "cleaning";

// PR-2 — the stage's own layout. The phone and the flow graph are no longer
// two components parked beside each other: they are one demonstration read
// left to right, message → phone → HIRA → systems. Two changes make that
// read rather than just describing it — the columns are sized so the phone
// leads and the graph follows at a supporting weight, and the connectors
// begin at the hub rather than at the container edge, so the eye is handed
// from one to the next.
const STAGE_LAYOUT =
  "flex w-full flex-col items-center gap-10 lg:min-h-[560px] lg:flex-row lg:items-center lg:justify-between lg:gap-8";
// The phone steps down at lg and back up at xl. Both stage columns were
// shrink-0, so at 1280 — where the grid's second track is ~140px narrower
// than at 1440 — their fixed widths summed past the track and the system
// rows ran off the right edge of the viewport.
const PHONE_COLUMN = "w-full max-w-[264px] shrink-0 sm:max-w-[300px] lg:max-w-[300px] xl:max-w-[348px]";
// The conversation fills the device and grows upward, the way a real thread
// does. min-h is gone: PhoneFrame now owns the device's aspect ratio, so the
// screen can no longer change height between beats and the stage cannot jump.
// The date divider is pinned to the top and the messages pushed to the bottom
// by `mt-auto` on their own group — a single justify-end would have dragged
// the divider down with them and left the screen looking empty above.
const PHONE_SCREEN = "relative flex flex-1 flex-col overflow-hidden px-3.5 pb-2 pt-3";
const PHONE_THREAD = "mt-auto flex flex-col gap-2";
// Not shrink-0: the flow takes whatever the phone leaves, so a narrower
// viewport costs the graph width rather than pushing it off-screen.
const FLOW_COLUMN = "w-full max-w-[420px] lg:min-w-0 lg:max-w-[500px] lg:flex-1";

// Timestamps are presentation, not scenario data — every scenario is the
// same two-message exchange a minute apart, and threading a clock through
// the beat engine would be state for nothing. Matched to PhoneFrame's own
// status-bar time so the device reads as internally consistent.
const MSG_TIME = "9:41";
const REPLY_TIME = "9:42";
const FOLLOW_UP_TIME = "9:42";
const CONFIRM_TIME = "9:43";

// Sprint 66 PR-3 — `key={scenarioId}` at the call site (see Hero, which
// owns the selector) remounts this whole widget on scenario change: every
// useState here reinitializes to its default and every effect's cleanup
// runs before the new instance's effects fire. That's the entire
// reset-and-restart mechanism — no manual "reset on scenario change"
// effect needed, no risk of a stale timer reading the new scenario's
// (possibly shorter) beats array.
//
// PR-2 changed nothing below this line about *when* things happen: the beat
// walker, the pause-on-hover/focus, the tab-visibility guard, the in-view
// gate and the reduced-motion branch are all as they were. Only what a given
// `status` renders as has changed.
export function OrchestrationStage({ scenarioId }: { scenarioId: ScenarioId }) {
  const reducedMotion = useReducedMotion();
  // DESIGN-MOTION-001 §7.3: at rest until scrolled into view, then alive;
  // pauses again if scrolled away.
  const viewRef = useRef<HTMLDivElement>(null);
  // Continuous (not once): the beat walker pauses whenever the stage leaves
  // the viewport and resumes when it returns.
  const inView = useInView(viewRef, { amount: 0.15 });
  const scenario = SCENARIOS[scenarioId];
  const [beatIndex, setBeatIndex] = useState(0);
  const [messageVisible, setMessageVisible] = useState(false);
  const [status, setStatus] = useState<Record<SystemId, SystemStatus>>(IDLE_STATUS);
  const [settled, setSettled] = useState(false);
  const [replyVisible, setReplyVisible] = useState(false);
  const [followUpVisible, setFollowUpVisible] = useState(false);
  const [confirmVisible, setConfirmVisible] = useState(false);
  const [closingVisible, setClosingVisible] = useState(false);
  const [paused, setPaused] = useState(false);
  // v0.69 — the pointer is over the device. Drives the graph's own reaction so
  // the two halves respond as one object, not two hover targets.
  const [engaged, setEngaged] = useState(false);
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
        setFollowUpVisible(false);
        setConfirmVisible(false);
        setClosingVisible(false);
        setBeatIndex(0);
        return;
      }
      const beat = scenario.beats[nextIndex];
      if (beat.message) setMessageVisible(true);
      if (beat.systems) setStatus((prev) => ({ ...prev, ...beat.systems }));
      if (beat.settled) setSettled(true);
      if (beat.reply) setReplyVisible(true);
      if (beat.followUp) setFollowUpVisible(true);
      if (beat.confirm) setConfirmVisible(true);
      if (beat.closing) setClosingVisible(true);
      setBeatIndex(nextIndex);
    }, scenario.beats[beatIndex].hold);
    return () => clearTimeout(timer);
  }, [beatIndex, paused, tabHidden, reducedMotion, inView, scenario]);

  const anyActive = Object.values(status).some((s) => s === "active");
  const hubState = settled ? "success" : anyActive ? "working" : "idle";
  // The conversation shows HIRA composing for exactly the window the graph
  // is busy — the phone and the graph narrating the same instant is what
  // makes them one demonstration rather than two.
  const typing = anyActive && !replyVisible && !closingVisible;
  // HIRA composes again between the customer's thanks and the confirmation —
  // the same cue in the same place, so the second exchange behaves like the
  // first rather than appearing instantly.
  const typingConfirm = followUpVisible && !confirmVisible && !closingVisible;

  const summary =
    `Demo: a customer messages HIRA asking, "${scenario.customerMessage}" HIRA coordinates four ` +
    "connected systems — CRM, Knowledge, Calendar, and Team — each working independently before " +
    `settling together in one synchronized moment and sending a reply: "${scenario.replyMessage}" One ` +
    "message, four systems, zero manual work.";

  const rows = (resolved: boolean) =>
    SYSTEMS.map((sys) => {
      const state = resolved ? "done" : status[sys.id];
      return (
        <SystemRow
          key={sys.id}
          icon={sys.icon}
          label={sys.label}
          role={sys.role}
          status={state}
          statusText={state === "done" ? sys.doneText : sys.workingText}
        />
      );
    });

  const phone = (children: React.ReactNode) => (
    <div aria-hidden="true" className={PHONE_COLUMN}>
      <DeviceShell onEngagedChange={setEngaged}>
        {(glare, chrome) => (
          <PhoneFrame time={MSG_TIME} glare={glare} chrome={chrome}>
            <ChatHeader name="Priya" presence="online" />
            <div className={PHONE_SCREEN}>
              <DateDivider label="Today" />
              <div className={PHONE_THREAD}>{children}</div>
            </div>
            <Composer style={chrome?.composer} />
          </PhoneFrame>
        )}
      </DeviceShell>
    </div>
  );

  if (reducedMotion) {
    return (
      <div role="img" aria-label={summary} className={STAGE_LAYOUT}>
        {phone(
          <>
            <CustomerBubble text={scenario.customerMessage} time={MSG_TIME} />
            <ReplyBubble text={scenario.replyMessage} time={REPLY_TIME} />
            <CustomerBubble text={scenario.followUpMessage} time={FOLLOW_UP_TIME} />
            <ReplyBubble text={scenario.confirmMessage} time={CONFIRM_TIME} />
          </>,
        )}
        <div aria-hidden="true" className={FLOW_COLUMN}>
          <FlowGraph status={DONE_STATUS} hubState="success" settled={false}>
            {rows(true)}
          </FlowGraph>
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
      // v0.69 — hover no longer pauses. It used to, so that a reader could
      // stop the loop and study it; but the device is now the page's
      // interactive object, and freezing the thing someone just reached for
      // is the opposite of it coming alive.
      //
      // Focus keeps the pause. That matters beyond preference: the demo
      // auto-plays and loops indefinitely, which is exactly what WCAG 2.2.2
      // (Pause, Stop, Hide) requires a mechanism for, and focus-to-pause was
      // the only mechanism this page had. Moving it to keyboard-only keeps
      // the obligation met while freeing the pointer for the interaction.
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      {phone(
        <>
          {messageVisible && !closingVisible && (
            <CustomerBubble text={scenario.customerMessage} time={MSG_TIME} />
          )}
          {typing && <TypingBubble />}
          {replyVisible && !closingVisible && (
            <ReplyBubble text={scenario.replyMessage} time={REPLY_TIME} />
          )}
          {followUpVisible && !closingVisible && (
            <CustomerBubble text={scenario.followUpMessage} time={FOLLOW_UP_TIME} />
          )}
          {typingConfirm && <TypingBubble />}
          {confirmVisible && !closingVisible && (
            <ReplyBubble text={scenario.confirmMessage} time={CONFIRM_TIME} />
          )}
          {closingVisible && <ClosingLine />}
        </>,
      )}

      <div aria-hidden="true" className={FLOW_COLUMN}>
        <FlowGraph status={status} hubState={hubState} settled={settled} engaged={engaged}>
          {rows(false)}
        </FlowGraph>
      </div>
    </div>
  );
}
const SCENARIO_ORDER: ScenarioId[] = ["cleaning", "dental", "pricing", "escalation"];
// Phase 2 — the emoji are gone. 🧹🦷💰🚨 were the least enterprise thing on
// the page: they render as a different typeface at a different weight in a
// different colour on every platform, so they were also the one element whose
// appearance the design system did not control. Nothing replaces them — not
// lucide glyphs either, since four icons in a row of four short words is
// decoration competing with the label. The chips now carry their own weight
// through type and the glass material, which is what the rest of the page
// does.

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
              "px-3.5 py-1.5 text-[0.8125rem] font-medium tracking-[0.01em] peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-background",
              // Signal & Depth PR-7 — unselected chips had no hover feedback
              // at all beyond the label's own cursor:pointer, unlike every
              // other clickable control in this app (Button, Card
              // interactive both pair hover with a visible state change).
              // Reuses Button's own outline-variant hover language
              // (hover:bg-accent hover:text-accent-foreground) rather than
              // inventing a new one. The selected chip is left alone — it's
              // already the active state, nothing new to hint at on hover.
              // Liquid Glass PR-1 — the material goes on the *unselected*
              // chips only. Glass is a deferring surface; the selected chip
              // is the one piece of state this control exists to show, so
              // it stays the solid default Badge and gains contrast from
              // the others receding. hover:bg-accent still wins over the
              // glass fill (later in the cascade), so PR-7's hover
              // affordance is unchanged.
              scenarioId !== id &&
                "glass border-[color:var(--glass-border)] hover:bg-accent hover:text-accent-foreground",
            )}
          >
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
