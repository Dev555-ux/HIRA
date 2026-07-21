"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

// HIRA's signature behavior, not a chat demo: one message reaches six real
// business systems, each begins and finishes its own work at its own pace
// (deliberately overlapping — colleagues working at once, not a queue), and
// then — the one moment this whole component exists to produce — every
// system settles into the same resting state in the exact same instant.
// That synchronized settle is driven by a single boolean flip, so it is
// genuinely simultaneous, not staggered to look that way. The customer's
// reply is the smallest, last thing on screen — a consequence, not the
// product.
type SystemId = "knowledge" | "crm" | "inventory" | "finance" | "calendar" | "team";
type SystemStatus = "idle" | "active" | "done";

// Fixed-pixel stage, not percentages: at extreme anchor points (12%, 94%) a
// fluid-width container leaves less physical clearance than a pill or label
// actually needs — verified via real Playwright screenshots at 390px and
// 834px widths that the trigger pill and the Knowledge label clipped past
// the viewport edge. A fixed canvas wrapped in overflow-x-auto guarantees
// full clearance at every anchor regardless of viewport width, scrolling
// horizontally on narrow screens instead of clipping.
const CANVAS_WIDTH = 1000;
const CANVAS_HEIGHT = 420;

const SYSTEMS: { id: SystemId; label: string; doneLabel: string; x: number }[] = [
  { id: "knowledge", label: "Knowledge", doneLabel: "Verified", x: 70 },
  { id: "crm", label: "CRM", doneLabel: "Updated", x: 242 },
  { id: "inventory", label: "Inventory", doneLabel: "Confirmed", x: 414 },
  { id: "finance", label: "Finance", doneLabel: "Calculated", x: 586 },
  { id: "calendar", label: "Calendar", doneLabel: "Booked", x: 758 },
  { id: "team", label: "Human Team", doneLabel: "Notified", x: 930 },
];

const IDLE_STATUS: Record<SystemId, SystemStatus> = {
  knowledge: "idle",
  crm: "idle",
  inventory: "idle",
  finance: "idle",
  calendar: "idle",
  team: "idle",
};

const DONE_STATUS: Record<SystemId, SystemStatus> = {
  knowledge: "done",
  crm: "done",
  inventory: "done",
  finance: "done",
  calendar: "done",
  team: "done",
};

const TRIGGER_POS = { x: 160, y: 90 };
const REPLY_POS = { x: 840, y: 90 };
const NODE_Y = 280;

type Beat = {
  hold: number;
  message?: boolean;
  systems?: Partial<Record<SystemId, SystemStatus>>;
  settled?: boolean;
  reply?: boolean;
  closing?: boolean;
};

// Every hold below is how long the CURRENT beat stays before the next one
// fires — timings are staggered deliberately so several systems are
// active at once (see the overlap between knowledge/crm/inventory/finance,
// and again between calendar/team), never a rigid one-at-a-time queue.
const BEATS: Beat[] = [
  { hold: 1500 }, // Scene 1 — idle, quiet, nothing moves
  { hold: 500, message: true }, // Scene 2 — the message arrives, small, off-center
  { hold: 300 }, // a breath before the business reacts
  { hold: 600, systems: { knowledge: "active" } },
  { hold: 200, systems: { crm: "active" } },
  { hold: 500, systems: { inventory: "active" } },
  { hold: 100, systems: { finance: "active" } },
  { hold: 300, systems: { knowledge: "done" } },
  { hold: 100, systems: { calendar: "active" } },
  { hold: 300, systems: { crm: "done" } },
  { hold: 200, systems: { inventory: "done" } },
  { hold: 100, systems: { team: "active" } },
  { hold: 800, systems: { finance: "done" } },
  { hold: 400, systems: { calendar: "done", team: "done" } },
  { hold: 1200, settled: true }, // Scene 5 — the signature moment: everything settles together
  { hold: 2200, reply: true }, // Scene 6 — the reply, last and smallest
  { hold: 3200, closing: true }, // Scene 7 — "One message. Six business systems. Zero manual work."
  { hold: 600 }, // hold before the loop resets
];

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

function Cables({ status }: { status: Record<SystemId, SystemStatus> }) {
  return (
    <svg
      viewBox={`0 0 ${CANVAS_WIDTH} ${CANVAS_HEIGHT}`}
      className="absolute inset-0 h-full w-full"
      aria-hidden="true"
    >
      {SYSTEMS.map((sys) => {
        if (status[sys.id] === "idle") return null;
        return (
          <line
            key={sys.id}
            x1={TRIGGER_POS.x}
            y1={TRIGGER_POS.y}
            x2={sys.x}
            y2={NODE_Y}
            vectorEffect="non-scaling-stroke"
            strokeWidth={1}
            className={cn(
              "transition-colors duration-700",
              status[sys.id] === "active" ? "stroke-primary" : "stroke-border",
            )}
          />
        );
      })}
    </svg>
  );
}

function SystemNode({ sys, status, settled }: { sys: (typeof SYSTEMS)[number]; status: SystemStatus; settled: boolean }) {
  return (
    <div
      className="absolute flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-2"
      style={{ left: sys.x, top: NODE_Y }}
    >
      <span
        className={cn(
          "size-3.5 rounded-full border transition-all duration-500",
          status === "idle" && "border-border/50",
          status === "active" && "scale-125 border-primary bg-primary/25",
          status === "done" && !settled && "border-success bg-success/15",
          status === "done" && settled && "border-foreground/40 bg-foreground/10",
        )}
      />
      <span
        className={cn(
          "text-[11px] uppercase tracking-wide transition-colors duration-500",
          status === "idle" ? "text-muted-foreground/35" : "text-muted-foreground",
        )}
      >
        {sys.label}
      </span>
      <span
        className={cn(
          "text-[10px] transition-opacity duration-500",
          status === "done" ? "opacity-100" : "opacity-0",
          settled ? "text-muted-foreground" : "text-success",
        )}
      >
        {sys.doneLabel}
      </span>
    </div>
  );
}

function Pill({ x, y, text }: { x: number; y: number; text: string }) {
  return (
    <div
      className="animate-fade-in absolute -translate-x-1/2 -translate-y-1/2"
      style={{ left: x, top: y }}
    >
      <div className="flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground">
        <span className="size-1.5 shrink-0 rounded-full bg-success" />
        {text}
      </div>
    </div>
  );
}

function ClosingLine() {
  return (
    <div className="animate-fade-in absolute inset-0 flex flex-col items-center justify-center gap-3 bg-background px-6 text-center">
      <p className="text-sm text-muted-foreground">One message. Six business systems. Zero manual work.</p>
      <p className="text-2xl font-semibold tracking-tight">This is HIRA.</p>
    </div>
  );
}

function DemoWidget() {
  const reducedMotion = useReducedMotion();
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
    if (paused || tabHidden || reducedMotion) return;
    const timer = setTimeout(() => {
      const nextIndex = beatIndex + 1;
      if (nextIndex >= BEATS.length) {
        setMessageVisible(false);
        setStatus(IDLE_STATUS);
        setSettled(false);
        setReplyVisible(false);
        setClosingVisible(false);
        setBeatIndex(0);
        return;
      }
      const beat = BEATS[nextIndex];
      if (beat.message) setMessageVisible(true);
      if (beat.systems) setStatus((prev) => ({ ...prev, ...beat.systems }));
      if (beat.settled) setSettled(true);
      if (beat.reply) setReplyVisible(true);
      if (beat.closing) setClosingVisible(true);
      setBeatIndex(nextIndex);
    }, BEATS[beatIndex].hold);
    return () => clearTimeout(timer);
  }, [beatIndex, paused, tabHidden, reducedMotion]);

  const summary =
    "Demo: a WhatsApp message triggers six business systems — Knowledge, CRM, Inventory, Finance, Calendar, and Human Team — each working independently before settling together in one synchronized moment and producing a reply. One message, six systems, zero manual work.";

  if (reducedMotion) {
    return (
      <div role="img" aria-label={summary} className="w-full overflow-x-auto">
        <div
          aria-hidden="true"
          className="relative mx-auto"
          style={{ width: CANVAS_WIDTH, height: CANVAS_HEIGHT }}
        >
          <Cables status={DONE_STATUS} />
          {SYSTEMS.map((sys) => (
            <SystemNode key={sys.id} sys={sys} status="done" settled />
          ))}
          <Pill x={TRIGGER_POS.x} y={TRIGGER_POS.y} text="Do you have anything in a BMW X7?" />
          <Pill x={REPLY_POS.x} y={REPLY_POS.y} text="Booked for tomorrow, 4:00 PM." />
        </div>
      </div>
    );
  }

  return (
    <div
      role="group"
      aria-label={`${summary} Animation pauses while hovered or focused.`}
      tabIndex={0}
      className="rounded-2xl outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <div className="overflow-x-auto">
        <div
          aria-hidden="true"
          className="relative mx-auto"
          style={{ width: CANVAS_WIDTH, height: CANVAS_HEIGHT }}
        >
          <Cables status={status} />
          <div key={settled ? "settled" : "working"} className={cn(settled && "animate-signature-settle")}>
            {SYSTEMS.map((sys) => (
              <SystemNode key={sys.id} sys={sys} status={status[sys.id]} settled={settled} />
            ))}
          </div>
          {messageVisible && !closingVisible && (
            <Pill x={TRIGGER_POS.x} y={TRIGGER_POS.y} text="Do you have anything in a BMW X7?" />
          )}
          {replyVisible && !closingVisible && (
            <Pill x={REPLY_POS.x} y={REPLY_POS.y} text="Booked for tomorrow, 4:00 PM." />
          )}
          {closingVisible && <ClosingLine />}
        </div>
      </div>
    </div>
  );
}

// Section-level wrapper: quiet, industrial restraint rather than another
// dark "spotlight" stage — generous vertical space and a thin top/bottom
// rule set this section apart, not a mood-lit background. Deliberately no
// eyebrow label above the stage this time: the animation explains itself,
// it isn't captioned first.
export function SignatureDemo() {
  return (
    <section className="border-y border-border/60 py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <DemoWidget />
      </div>
    </section>
  );
}
