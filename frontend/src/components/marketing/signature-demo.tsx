"use client";

import { useEffect, useState } from "react";
import { useInView } from "@/hooks/use-in-view";
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

// Two coordinate sets per system, not one reflowed at every width: below
// tablet width (based on real Playwright screenshots, verified at 390px) six
// nodes in a single row need more physical space than a phone has, so they
// arrange into two compact rows instead of scrolling horizontally. Desktop
// and tablet keep the original wide single-row canvas.
const CANVAS_WIDTH = 1000;
const CANVAS_COMPACT_WIDTH = 340;
const CANVAS_HEIGHT = 420;
const NODE_Y = 280;

const TRIGGER_POS_WIDE = { x: 160, y: 90 };
const REPLY_POS_WIDE = { x: 840, y: 90 };
const TRIGGER_POS_COMPACT = { x: 170, y: 32 };
const REPLY_POS_COMPACT = { x: 170, y: 84 };

const SYSTEMS: {
  id: SystemId;
  label: string;
  workingText: string;
  doneText: string;
  xWide: number;
  xCompact: number;
  yCompact: number;
}[] = [
  { id: "knowledge", label: "Knowledge", workingText: "Searching…", doneText: "Verified", xWide: 70, xCompact: 60, yCompact: 190 },
  { id: "crm", label: "CRM", workingText: "Finding customer…", doneText: "Customer found", xWide: 242, xCompact: 170, yCompact: 190 },
  { id: "inventory", label: "Inventory", workingText: "Checking stock…", doneText: "BMW X7 available", xWide: 414, xCompact: 280, yCompact: 190 },
  { id: "finance", label: "Finance", workingText: "Preparing quote…", doneText: "Quote ready", xWide: 586, xCompact: 60, yCompact: 330 },
  { id: "calendar", label: "Calendar", workingText: "Checking availability…", doneText: "Tuesday · 2 PM", xWide: 758, xCompact: 170, yCompact: 330 },
  { id: "team", label: "Human Team", workingText: "Preparing handoff…", doneText: "Sales notified", xWide: 930, xCompact: 280, yCompact: 330 },
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

function triggerPos(compact: boolean) {
  return compact ? TRIGGER_POS_COMPACT : TRIGGER_POS_WIDE;
}
function replyPos(compact: boolean) {
  return compact ? REPLY_POS_COMPACT : REPLY_POS_WIDE;
}
function canvasWidth(compact: boolean) {
  return compact ? CANVAS_COMPACT_WIDTH : CANVAS_WIDTH;
}
function nodePos(sys: (typeof SYSTEMS)[number], compact: boolean) {
  return compact ? { x: sys.xCompact, y: sys.yCompact } : { x: sys.xWide, y: NODE_Y };
}

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
// and again between calendar/team), never a rigid one-at-a-time queue. The
// 700ms settled hold is the emotional payoff: everything goes quiet before
// the reply arrives, not immediately after.
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
  { hold: 700, settled: true }, // Scene 5 — the signature moment: everything settles together, then a quiet pause
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

// Below tablet width (verified via Playwright at 390px) a single row of six
// nodes only fit via horizontal scrolling, which works but isn't a great
// experience — so phones get a compact two-row arrangement instead. Checked
// only in an effect, like useReducedMotion, so the server-rendered markup
// never depends on viewport width and hydration can't mismatch.
function useIsCompact() {
  const [compact, setCompact] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(max-width: 767px)");
    setCompact(query.matches);
    const onChange = (e: MediaQueryListEvent) => setCompact(e.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);
  return compact;
}

function Cables({ status, compact }: { status: Record<SystemId, SystemStatus>; compact: boolean }) {
  const trigger = triggerPos(compact);
  return (
    <svg
      viewBox={`0 0 ${canvasWidth(compact)} ${CANVAS_HEIGHT}`}
      className="absolute inset-0 h-full w-full"
      aria-hidden="true"
    >
      {SYSTEMS.map((sys) => {
        const state = status[sys.id];
        if (state === "idle") return null;
        const { x, y } = nodePos(sys, compact);

        if (state === "active") {
          // Two lines sharing one path, not one dashed line: a dim, fully
          // continuous base (the connection itself, always visible) plus a
          // bright dash riding on top of it (the pulse — work moving through
          // that connection). A single sparse dasharray would make the
          // connection itself flicker in and out; this keeps it solid.
          return (
            <g key={sys.id}>
              <line x1={trigger.x} y1={trigger.y} x2={x} y2={y} vectorEffect="non-scaling-stroke" strokeWidth={1} className="stroke-primary/25" />
              <line
                x1={trigger.x}
                y1={trigger.y}
                x2={x}
                y2={y}
                pathLength={100}
                vectorEffect="non-scaling-stroke"
                strokeWidth={1}
                strokeDasharray="6 94"
                className="stroke-primary animate-signature-pulse"
              />
            </g>
          );
        }

        return (
          <line
            key={sys.id}
            x1={trigger.x}
            y1={trigger.y}
            x2={x}
            y2={y}
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
  compact,
}: {
  sys: (typeof SYSTEMS)[number];
  status: SystemStatus;
  settled: boolean;
  statusTextVisible: boolean;
  compact: boolean;
}) {
  const { x, y } = nodePos(sys, compact);
  // One line of evidence, never more: the working verb while a system is
  // active, then its own completion ("→ Verified") once done. In the live
  // animation this line fades away once the whole business settles together
  // (statusTextVisible=false), so the interface goes quiet before the reply.
  // The reduced-motion static frame is the one exception — it's the only
  // frame that user ever sees, so it keeps every line visible regardless of
  // settled, otherwise the evidence of what happened would never be shown.
  const statusText = status === "active" ? sys.workingText : status === "done" ? `→ ${sys.doneText}` : "";
  const showStatus = status !== "idle" && statusTextVisible;

  return (
    <div
      className="absolute flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-2"
      style={{ left: x, top: y }}
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
          "block overflow-hidden text-ellipsis whitespace-nowrap text-[10px] transition-opacity duration-500",
          compact ? "max-w-[100px]" : "max-w-[150px]",
          showStatus ? "opacity-100" : "opacity-0",
          status === "done" ? "text-success" : "text-muted-foreground/70",
        )}
      >
        {statusText}
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
  const compact = useIsCompact();
  // DESIGN-MOTION-001 §7.3: at rest until scrolled into view, then alive;
  // pauses again if scrolled away — battery and honesty, same reasoning as
  // the existing tab-hidden guard below, just for the viewport instead of
  // the tab.
  const { ref: viewRef, inView } = useInView<HTMLDivElement>({ once: false, rootMargin: "0px" });
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
  }, [beatIndex, paused, tabHidden, reducedMotion, inView]);

  const summary =
    "Demo: a WhatsApp message triggers six business systems — Knowledge, CRM, Inventory, Finance, Calendar, and Human Team — each working independently before settling together in one synchronized moment and producing a reply. One message, six systems, zero manual work.";

  const trigger = triggerPos(compact);
  const reply = replyPos(compact);
  const width = canvasWidth(compact);

  if (reducedMotion) {
    return (
      <div role="img" aria-label={summary} className="w-full overflow-x-auto">
        <div
          aria-hidden="true"
          className="relative mx-auto"
          style={{ width, height: CANVAS_HEIGHT }}
        >
          <Cables status={DONE_STATUS} compact={compact} />
          {SYSTEMS.map((sys) => (
            <SystemNode
              key={sys.id}
              sys={sys}
              status="done"
              settled
              statusTextVisible
              compact={compact}
            />
          ))}
          <Pill x={trigger.x} y={trigger.y} text="Do you have anything in a BMW X7?" />
          <Pill x={reply.x} y={reply.y} text="Booked for tomorrow, 4:00 PM." />
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
          style={{ width, height: CANVAS_HEIGHT }}
        >
          <Cables status={status} compact={compact} />
          <div key={settled ? "settled" : "working"} className={cn(settled && "animate-signature-settle")}>
            {SYSTEMS.map((sys) => (
              <SystemNode
                key={sys.id}
                sys={sys}
                status={status[sys.id]}
                settled={settled}
                statusTextVisible={!settled}
                compact={compact}
              />
            ))}
          </div>
          {messageVisible && !closingVisible && (
            <Pill x={trigger.x} y={trigger.y} text="Do you have anything in a BMW X7?" />
          )}
          {replyVisible && !closingVisible && (
            <Pill x={reply.x} y={reply.y} text="Booked for tomorrow, 4:00 PM." />
          )}
          {closingVisible && <ClosingLine />}
        </div>
      </div>
    </div>
  );
}

// Section-level wrapper: quiet, industrial restraint rather than another
// dark "spotlight" stage — generous vertical space and a thin top rule set
// this section apart, not a mood-lit background. Deliberately no eyebrow
// label above the stage this time: the animation explains itself, it isn't
// captioned first.
//
// Sprint 68: was `border-y border-border/60` — the translucent border was
// the only non-full-strength divider on the page, and pairing it with
// Trust's own border-t immediately below (0 margin between them) produced
// a doubled 2px seam where every other section boundary on the page is a
// single 1px line (Sprint 67 audit). A single full-strength border-t
// matches every other divider and still marks the Hero → Signature Demo
// edge; Trust's own border-t continues to mark the edge below it, same as
// it always has.
export function SignatureDemo() {
  return (
    <section className="border-t py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <DemoWidget />
      </div>
    </section>
  );
}
