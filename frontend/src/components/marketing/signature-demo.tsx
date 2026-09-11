"use client";

import { BookOpen, Calendar, UserCheck, Users } from "lucide-react";
import { useEffect, useState } from "react";
import type { LucideIcon } from "lucide-react";
import { AIAvatar } from "@/components/ui/ai-avatar";
import { Card } from "@/components/ui/card";
import { useInView } from "@/hooks/use-in-view";
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
    chipLabel: "Booking",
    customerMessage: "Do you have availability for a cleaning this Thursday?",
    replyMessage: "Thursday at 10:00 AM works — you're all set!",
    beats: CLEANING_BEATS,
  },
  dental: {
    id: "dental",
    chipLabel: "Clinic",
    customerMessage: "Can I book a consultation with Dr. Martinez tomorrow afternoon?",
    replyMessage: "Dr. Martinez has an opening tomorrow at 3:30 PM — you're all set!",
    beats: DENTAL_BEATS,
  },
  pricing: {
    id: "pricing",
    chipLabel: "Knowledge",
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

// Default to today's scenario — no selector exists yet (a later PR), so
// this is the only one ever rendered right now.
export const DEFAULT_SCENARIO_ID: ScenarioId = "cleaning";

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

// Cables radiate from the hub outward — HIRA reaching into each system,
// not systems reporting in independently. Same two-line technique as
// before (a dim continuous base + a bright travelling dash on top) so the
// connection itself never flickers, only the pulse riding on it.
function Cables({ status }: { status: Record<SystemId, SystemStatus> }) {
  return (
    <svg viewBox="0 0 100 100" className="absolute inset-0 h-full w-full" aria-hidden="true">
      {SYSTEMS.map((sys) => {
        const state = status[sys.id];
        if (state === "idle") return null;

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

        return (
          <line
            key={sys.id}
            x1={HUB.x}
            y1={HUB.y}
            x2={sys.x}
            y2={sys.y}
            vectorEffect="non-scaling-stroke"
            strokeWidth={1}
            className="stroke-border transition-colors duration-700"
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
          "flex size-8 items-center justify-center rounded-full border bg-card transition-all duration-500 [&_svg]:size-4",
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
          "text-[11px] font-medium uppercase tracking-wide transition-colors duration-500",
          status === "idle" ? "text-muted-foreground/35" : "text-muted-foreground",
        )}
      >
        {sys.label}
      </span>
      <span
        className={cn(
          "block text-[10px] leading-tight transition-opacity duration-500",
          showStatus ? "opacity-100" : "opacity-0",
          status === "done" ? "text-success" : "text-muted-foreground/70",
        )}
      >
        {statusText}
      </span>
    </div>
  );
}

function CustomerBubble({ text }: { text: string }) {
  return (
    <div className="animate-fade-in flex justify-start">
      <div className="max-w-[85%] rounded-md bg-muted px-3 py-2 text-sm">{text}</div>
    </div>
  );
}

function ReplyBubble({ text }: { text: string }) {
  return (
    <div className="animate-fade-in flex justify-end">
      <div className="max-w-[85%] rounded-md bg-secondary px-3 py-2 text-sm text-secondary-foreground">
        {text}
      </div>
    </div>
  );
}

function ClosingLine() {
  return (
    <div className="animate-fade-in absolute inset-0 flex flex-col items-center justify-center gap-3 bg-card px-6 text-center">
      <p className="text-sm text-muted-foreground">One message. Four business systems. Zero manual work.</p>
      <p className="text-2xl font-semibold tracking-tight">This is HIRA.</p>
    </div>
  );
}

function DemoWidget() {
  const reducedMotion = useReducedMotion();
  // DESIGN-MOTION-001 §7.3: at rest until scrolled into view, then alive;
  // pauses again if scrolled away.
  const { ref: viewRef, inView } = useInView<HTMLDivElement>({ once: false, rootMargin: "0px" });
  const scenario = SCENARIOS[DEFAULT_SCENARIO_ID];
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
      <div className="mx-auto w-full max-w-md">
        <Card role="img" aria-label={summary} className="space-y-4 overflow-hidden p-6 sm:p-8">
          <div aria-hidden="true" className="space-y-4">
            <CustomerBubble text={scenario.customerMessage} />
            <div className="relative mx-auto aspect-square w-full max-w-[280px] sm:max-w-[320px]">
              <Cables status={DONE_STATUS} />
              <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
                <AIAvatar name="HIRA" size="xl" state="success" />
              </div>
              {SYSTEMS.map((sys) => (
                <SystemNode key={sys.id} sys={sys} status="done" settled statusTextVisible />
              ))}
            </div>
            <ReplyBubble text={scenario.replyMessage} />
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div
      ref={viewRef}
      role="group"
      aria-label={`${summary} Animation pauses while hovered or focused.`}
      tabIndex={0}
      className="mx-auto w-full max-w-md rounded-2xl outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <Card className="relative space-y-4 overflow-hidden p-6 sm:p-8">
        {messageVisible && !closingVisible && <CustomerBubble text={scenario.customerMessage} />}

        <div aria-hidden="true" className="relative mx-auto aspect-square w-full max-w-[280px] sm:max-w-[320px]">
          <Cables status={status} />
          <div
            className={cn(
              "absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2",
              settled && "animate-signature-settle",
            )}
          >
            <AIAvatar name="HIRA" size="xl" state={hubState} />
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

        {replyVisible && !closingVisible && <ReplyBubble text={scenario.replyMessage} />}
        {closingVisible && <ClosingLine />}
      </Card>
    </div>
  );
}

// Section-level wrapper: a narrower container than before (max-w-2xl, not
// max-w-6xl) — the radial layout is inherently more compact/vertical than
// the old wide horizontal flow, so a wide section around it just reads as
// empty space. Same quiet industrial framing (a single top rule, generous
// vertical padding) as every other section boundary on the page.
export function SignatureDemo() {
  return (
    <section className="border-t py-24 sm:py-32">
      <div className="mx-auto max-w-2xl px-4 sm:px-6">
        <DemoWidget />
      </div>
    </section>
  );
}
