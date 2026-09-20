"use client";

import { animate, AnimatePresence, useMotionValue, useSpring, useTransform } from "motion/react";
import * as m from "motion/react-m";
import { Check, Paperclip, Mic } from "lucide-react";
import { useCallback, useRef } from "react";
import { useReducedMotion } from "@/hooks/use-reduced-motion";
import { fadeUp, transition } from "@/lib/motion";
import type * as React from "react";
import type { LucideIcon } from "lucide-react";
import { AIAvatar } from "@/components/ui/ai-avatar";
import { cn } from "@/lib/utils";

// PR-2 — the stage's presentation layer, split out of signature-demo.tsx so
// that file stays the engine (scenarios, beats, the timer) and this one is
// purely how a given `status` looks. Nothing here holds state.

export type SystemStatus = "idle" | "active" | "done";

// ── Conversation ───────────────────────────────────────────────────────────

// A messaging UI, not a reproduction of one. Deliberately NOT WhatsApp: no
// green, no wallpaper texture, no tail-notch bubble, none of their iconography
// or wordmark. The cues used are the generic vocabulary every modern client
// shares — a contact row, asymmetric bubbles, right-aligned timestamps, a
// delivery/read tick, a composer bar. Outgoing is HIRA's own brand tint,
// which is the point: these replies are the product speaking.
export function ChatHeader({ name, presence }: { name: string; presence: string }) {
  return (
    <div className="flex items-center gap-2.5 border-b border-border/60 px-3.5 pb-2.5 pt-1">
      <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted text-[11px] font-semibold text-muted-foreground">
        {name.slice(0, 1)}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] font-semibold leading-tight">{name}</p>
        <p className="flex items-center gap-1 text-[10.5px] leading-tight text-muted-foreground">
          <span className="size-1.5 rounded-full bg-success" />
          {presence}
        </p>
      </div>
    </div>
  );
}

// Two ticks, overlapped. `read` tints them — the one cue in the conversation
// that carries colour on purpose, because "they saw it" is the moment the
// whole demo is selling.
function Ticks({ read }: { read: boolean }) {
  return (
    <span className={cn("relative inline-flex h-3 w-[15px] shrink-0", read ? "text-brand" : "text-muted-foreground")}>
      <Check className="absolute left-0 top-0 size-3" strokeWidth={3} />
      <Check className="absolute left-[5px] top-0 size-3" strokeWidth={3} />
    </span>
  );
}

function Meta({ time, ticks }: { time: string; ticks?: boolean }) {
  return (
    <span className="mt-0.5 flex items-center justify-end gap-1 text-[10px] leading-none text-muted-foreground">
      {time}
      {ticks && <Ticks read />}
    </span>
  );
}

export function CustomerBubble({ text, time }: { text: string; time: string }) {
  return (
    <m.div
      layout="position"
      transition={transition.enter}
      variants={fadeUp}
      initial="hidden"
      animate="show"
      className="flex justify-start"
    >
      <div className="max-w-[86%] rounded-2xl rounded-bl-md bg-muted px-3 py-2 shadow-e1">
        <p className="text-[13px] leading-snug">{text}</p>
        <Meta time={time} />
      </div>
    </m.div>
  );
}

export function ReplyBubble({ text, time }: { text: string; time: string }) {
  return (
    <m.div
      layout="position"
      transition={transition.enter}
      variants={fadeUp}
      initial="hidden"
      animate="show"
      className="flex justify-end"
    >
      {/* bg-brand/20 + text-foreground, not the brand/brand-foreground pair:
          at 20% the fill is a tint over the screen, so the readable pairing
          is against the screen's own foreground. Measured, not assumed. */}
      <div className="max-w-[86%] rounded-2xl rounded-br-md bg-brand/[0.26] px-3 py-2 shadow-e1 ring-1 ring-brand/30">
        <p className="text-[13px] leading-snug text-foreground">{text}</p>
        <Meta time={time} ticks />
      </div>
    </m.div>
  );
}

// The "HIRA is working" beat, shown in the conversation while the graph runs.
// Three dots is the one messaging convention worth keeping literally — it is
// universal, and inventing an alternative would cost comprehension for no
// gain. Purely decorative, and the stage is aria-hidden regardless.
export function TypingBubble() {
  return (
    <m.div
      layout="position"
      transition={transition.enter}
      variants={fadeUp}
      initial="hidden"
      animate="show"
      className="flex justify-end"
    >
      <div className="flex items-center gap-1 rounded-2xl rounded-br-md bg-brand/12 px-3 py-2.5 ring-1 ring-brand/20">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="size-1.5 rounded-full bg-brand/70"
            style={{ animation: `typing-dot 1.2s ${i * 0.16}s ease-in-out infinite` }}
          />
        ))}
      </div>
    </m.div>
  );
}

// A composer bar. Inert by design — it is scenery inside an aria-hidden
// stage, so it is a <div>, never a real input a keyboard could land in.
export function Composer({ style }: { style?: React.CSSProperties }) {
  return (
    // Second-closest layer to the glass after the island, so it travels
    // further than the thread behind it.
    <m.div style={style} className="relative z-10 flex items-center gap-2 px-3.5 pt-2.5">
      <Paperclip className="size-4 shrink-0 text-muted-foreground/70" aria-hidden="true" />
      <div className="glass flex h-8 flex-1 items-center rounded-full border border-[color:var(--glass-border)] px-3">
        <span className="text-[12px] text-muted-foreground/70">Message</span>
      </div>
      <Mic className="size-4 shrink-0 text-muted-foreground/70" aria-hidden="true" />
    </m.div>
  );
}

// A date separator. Small, but it is what stops a two-message thread reading
// as an empty screen with something stuck to the bottom: every messaging app
// puts one at the top of a day's conversation, so its presence is the cue
// that says "this is a thread" rather than "this is a mockup".
export function DateDivider({ label }: { label: string }) {
  return (
    <div className="flex justify-center">
      <span className="glass rounded-full border border-[color:var(--glass-border)] px-2.5 py-1 text-[10px] font-medium text-muted-foreground">
        {label}
      </span>
    </div>
  );
}

export function ClosingLine() {
  return (
    <div className="animate-fade-in absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-background px-6 text-center">
      <p className="text-[13px] text-muted-foreground">One message. Four business systems. Zero manual work.</p>
      <p className="text-xl font-semibold tracking-tight">This is HIRA.</p>
    </div>
  );
}

// ── Orchestration ──────────────────────────────────────────────────────────

// Row geometry, in px, shared by the list and the connector SVG. The two have
// to agree exactly or the curves land off their rows, so the numbers live in
// one place and the SVG derives its percentages from them rather than from a
// second set of hand-tuned constants.
const ROW_H = 70;
const ROW_GAP = 12;
export const FLOW_H = 4 * ROW_H + 3 * ROW_GAP; // 316

// Where the hub and the rows sit horizontally, as percentages of the flow
// column. Percentages (not px) because the connector SVG uses a 0–100 viewBox
// with preserveAspectRatio="none" — the same technique the old radial canvas
// used — so x positions must be resolution-independent. Stroke width is kept
// true with vectorEffect.
// The hub's gutter was 30% of the flow column — generous at 1440, but at
// 1280 it left the rows too narrow to hold a label and a description on one
// line. 24% still gives the connectors a readable run.
const HUB_X = 9;
const ROWS_X = 24;

const rowCenterPct = (i: number) => ((i * (ROW_H + ROW_GAP) + ROW_H / 2) / FLOW_H) * 100;

// One connector per system, hub → row. A cubic with both control points
// pulled horizontally gives the flat S the reference uses: it leaves the hub
// horizontally and arrives at the row horizontally, so the fan reads as
// routing rather than as spokes.
function Connectors({ status }: { status: Record<string, SystemStatus> }) {
  return (
    <svg
      className="absolute inset-0 h-full w-full"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      {SYSTEM_ORDER.map((id, i) => {
        const y = rowCenterPct(i);
        const d = `M ${HUB_X + 5} 50 C ${(HUB_X + ROWS_X) / 2 + 6} 50, ${(HUB_X + ROWS_X) / 2} ${y}, ${ROWS_X} ${y}`;
        const state = status[id];
        return (
          // data-system is a test seam: the old radial cables were
          // identifiable by their x2/y2 coordinates, which these curves do
          // not have. Naming the system is more durable than asserting on
          // path geometry that any future restyle would break.
          <g key={id} data-system={id}>
            {/* The topology at rest: always drawn, so "these four are wired
                to HIRA" is legible before any beat fires. */}
            <path
              d={d}
              fill="none"
              vectorEffect="non-scaling-stroke"
              strokeWidth={1}
              className="stroke-border"
            />
            {state !== "idle" && (
              <path
                d={d}
                fill="none"
                vectorEffect="non-scaling-stroke"
                strokeWidth={state === "active" ? 2 : 1.5}
                className={state === "done" ? "stroke-success/60" : "stroke-brand"}
                strokeDasharray={state === "active" ? "6 10" : undefined}
                style={state === "active" ? { animation: "cable-flow 1.1s linear infinite" } : undefined}
              />
            )}
          </g>
        );
      })}
    </svg>
  );
}

const SYSTEM_ORDER = ["crm", "knowledge", "calendar", "team"] as const;

export function SystemRow({
  icon: Icon,
  label,
  role,
  status,
  statusText,
}: {
  icon: LucideIcon;
  label: string;
  role: string;
  status: SystemStatus;
  statusText: string;
}) {
  return (
    <li
      style={{ height: ROW_H }}
      className={cn(
        // The fill is pushed to 88% opaque here, unlike every other glass
        // surface on the page. These rows sit directly over the key light's
        // brightest region, and at the default 62% the warm backdrop bled
        // through strongly enough to tint a green "done" border orange —
        // the state colour is the entire signal this component carries, so
        // it cannot be at the mercy of what happens to be behind it. The
        // sheen and refraction edge still read; only the transparency is
        // dialled back to where state survives.
        "glass flex items-center gap-3 rounded-2xl border px-3 [--glass-fill:color-mix(in_srgb,var(--card)_92%,transparent)]!",
        // PR-3 — the focal moment. Four rows carrying equal weight gave the
        // eye nowhere to land: state was legible but flat, so a visitor had
        // to read all four to find the one doing work. The row that is
        // *currently working* now physically lifts — elevation and a hair of
        // scale, not a new colour or a new element — so attention tracks the
        // work down the list on its own. Idle and done stay flat by design;
        // the lift is the signal, and a signal that is always on is not one.
        "transition-[border-color,background-color,box-shadow,transform] duration-[var(--motion-slow)] ease-[var(--ease-out-quart)]",
        status === "idle" && "border-[color:var(--glass-border)] opacity-80",
        status === "active" && "z-10 scale-[1.025] border-brand/80 bg-brand/[0.08] shadow-e4",
        status === "done" && "border-success/70 bg-success/[0.07] shadow-e1",
      )}
    >
      <span
        className={cn(
          "flex size-9 shrink-0 items-center justify-center rounded-xl border transition-colors duration-[var(--motion-slow)] [&_svg]:size-[18px]",
          status === "idle" && "border-border bg-muted/50 text-muted-foreground",
          status === "active" && "border-brand/75 bg-brand/15 text-brand",
          status === "done" && "border-success/70 bg-success/12 text-success",
        )}
      >
        <Icon aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-semibold leading-tight">{label}</p>
        {/* The second line swaps role → live status → outcome. One line, not
            two stacked, so the row height never changes and the connectors
            stay aligned with it. */}
        {/* T3.7 — below lg the connector cables are not rendered, so the
            travelling pulse that signals "work is moving" is absent exactly
            where the phone fills the screen, and this line used to swap
            between frames. Keyed on status so each state gets its own
            element; mode="wait" so the outgoing text clears before the
            incoming one arrives, which is what makes the change readable
            rather than a cross-fade of two strings in the same place. */}
        <AnimatePresence mode="wait" initial={false}>
          <m.p
            key={status}
            initial={{ opacity: 0, x: 4 }}
            animate={{ opacity: 1, x: 0, transition: transition.enter }}
            exit={{ opacity: 0, transition: transition.exit }}
            className={cn(
              "truncate text-[11.5px] leading-tight transition-colors duration-[var(--motion-slow)]",
              status === "done" ? "text-success" : status === "active" ? "text-brand" : "text-muted-foreground",
            )}
          >
            {status === "idle" ? role : statusText}
          </m.p>
        </AnimatePresence>
      </div>
      {status === "done" && (
        <Check className="size-4 shrink-0 text-success" strokeWidth={2.5} aria-hidden="true" />
      )}
    </li>
  );
}

export function FlowGraph({
  status,
  hubState,
  settled,
  engaged = false,
  children,
}: {
  status: Record<string, SystemStatus>;
  hubState: "idle" | "working" | "success";
  settled: boolean;
  // True while the pointer is over the device. The graph brightens its
  // connectors and lifts the hub by a hair — enough that the two halves read
  // as one object responding, not as two separate hover targets, and far too
  // little to compete with the device that is actually moving.
  engaged?: boolean;
  children: React.ReactNode;
}) {
  return (
    // Two arrangements, one component. At lg the hub sits left of the rows
    // with connectors fanning between them — the left-to-right reading the
    // brief asks for. Below lg that geometry has nowhere to go: at 390px the
    // hub's 11% left offset puts it half off the edge and the rows lose ~30%
    // of their width to a gutter, so the flow stacks instead — hub on top,
    // rows full-width beneath, connectors dropped entirely rather than drawn
    // at a size where they read as noise. The height is only fixed at lg,
    // because only the connector geometry depends on it.
    <div
      className="relative flex w-full flex-col items-center gap-5 lg:block lg:h-[var(--flow-h)]"
      style={{ "--flow-h": `${FLOW_H}px` } as React.CSSProperties}
    >
      <div
        className={cn(
          // Refinement — 80->100 was a 25% jump in the graph's weight at the
          // exact moment the phone starts moving, which made the two compete.
          // 88->100 is still felt as the scene waking up without pulling the
          // eye off the device that is actually doing something.
          "hidden transition-opacity duration-[var(--motion-slow)] ease-[var(--ease-out-quart)] lg:block",
          engaged ? "opacity-100" : "opacity-[0.88]",
        )}
      >
        <Connectors status={status} />
      </div>

      {/* Hub. At lg it is absolutely placed at exactly the percentage the
          connectors leave from, so the two can never drift apart. */}
      <div
        className={cn(
          "z-10 isolate lg:absolute lg:top-1/2 lg:-translate-x-1/2 lg:-translate-y-1/2",
          settled && "animate-signature-settle",
        )}
        style={{ left: `${HUB_X}%` }}
      >
        <div
          aria-hidden="true"
          className={cn(
            "absolute left-1/2 top-1/2 -z-10 size-24 -translate-x-1/2 -translate-y-1/2 rounded-full blur-xl transition-colors duration-[var(--motion-slow)]",
            hubState === "success" ? "bg-success/20" : hubState === "working" ? "bg-brand/25" : "bg-transparent",
          )}
        />
        <div
          className={cn(
            // Refinement — the hub's lift is gone. Two objects rising at once
            // reads as the page zooming; only the phone should move. The hub
            // keeps a shadow change alone, which registers as the scene
            // responding without a second thing in motion.
            "glass rounded-2xl border border-[color:var(--glass-border)] p-2 transition-[box-shadow] duration-[var(--motion-slow)] ease-[var(--ease-out-quart)]",
            engaged ? "shadow-e4" : "shadow-e3",
          )}
        >
          <AIAvatar name="HIRA" size="xl" state={hubState} />
        </div>
        <p className="mt-2 text-center text-[10px] font-bold uppercase tracking-[0.1em] text-muted-foreground">
          Core
        </p>
      </div>

      <ul
        className="flex w-full flex-col lg:absolute lg:inset-y-0 lg:right-0 lg:w-auto"
        style={{ left: `${ROWS_X}%`, gap: ROW_GAP }}
      >
        {children}
      </ul>
    </div>
  );
}

// ── Device interaction ─────────────────────────────────────────────────────

// v0.69 — the phone tilts toward the cursor, lifts, and its glass catches a
// moving highlight. Everything here is transform/opacity only, driven by
// framer-motion springs off two motion values, so it never touches layout and
// never re-renders React on pointer move — the whole interaction runs on the
// compositor.
//
// Restraint is the brief: 7 degrees of rotation, 10px of lift. Apple's own
// product pages sit around this; double it and the device reads as a toy. The
// springs are deliberately low-stiffness and high-damping — the device should
// feel heavy and settle, not snap or bounce. No overshoot at all: `bounce: 0`
// is what separates "physical" from "gaming UI".
// v0.69 refinement. Every number here came down.
//
// 7deg -> 4.5deg, and perspective 1400 -> 2200. Those two work together: a
// short perspective exaggerates foreshortening, so the near edge swells and
// the device reads as a plane being wobbled rather than an object being
// turned. A longer perspective with less rotation is what a real object seen
// from a normal distance actually does.
//
// The spring is softer and heavier (150/26/0.9 -> 105/30/1.15). The old one
// arrived slightly ahead of the cursor, which is exactly what reads as
// "following the mouse"; a heavier mass lags the pointer a little, and the
// lag is what makes it feel like a physical thing you are turning rather
// than a thing that is chasing you. Still zero overshoot.
const TILT_DEG = 4.5;
const LIFT_PX = 8;
const SETTLE = { stiffness: 105, damping: 30, mass: 1.15 } as const;

// The motion-driven pieces of hardware the shell hands to PhoneFrame. Typed
// as CSSProperties because each value is a MotionValue that framer resolves
// at paint; PhoneFrame never reads them, it only spreads them onto the right
// layer.
export type DeviceChrome = {
  railL: React.CSSProperties;
  railR: React.CSSProperties;
  glassEdgeA: React.CSSProperties;
  glassEdgeB: React.CSSProperties;
  glassEdgeEngaged: React.CSSProperties;
  island: React.CSSProperties;
  composer: React.CSSProperties;
  thread: React.CSSProperties;
  bg: React.CSSProperties;
};

export function DeviceShell({
  children,
  onEngagedChange,
}: {
  children: (glare: React.ReactNode, chrome?: DeviceChrome) => React.ReactNode;
  onEngagedChange?: (engaged: boolean) => void;
}) {
  const reducedMotion = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  // -0.5..0.5 on each axis, relative to the device's own box.
  const px = useMotionValue(0);
  const py = useMotionValue(0);
  const engaged = useMotionValue(0);

  const sx = useSpring(px, SETTLE);
  const sy = useSpring(py, SETTLE);
  const sEngaged = useSpring(engaged, SETTLE);

  // Tilt is inverted on X: pushing the cursor down should tip the *top* of
  // the device away, the way a hinged object behaves.
  const rotateY = useTransform(sx, [-0.5, 0.5], [-TILT_DEG, TILT_DEG]);
  const rotateX = useTransform(sy, [-0.5, 0.5], [TILT_DEG, -TILT_DEG]);
  const lift = useTransform(sEngaged, [0, 1], [0, -LIFT_PX]);
  const scale = useTransform(sEngaged, [0, 1], [1, 1.01]);
  // Screen depth. One flat parallax plane was the giveaway that the UI was
  // painted on rather than sitting under glass. Four layers now move by
  // different amounts, and the ordering is the physical one: layers nearer
  // the viewer travel further. The island is a cutout in the cover glass, so
  // it is the closest thing to the surface and moves most; the chat
  // background is the deepest and barely moves at all.
  //
  // The whole range is 0.6px to 3px. Beyond ~3px the layers visibly slide
  // against each other and the illusion inverts into "the UI is loose inside
  // the frame", which is worse than no parallax.
  // Written out rather than generated in a loop: these are hooks, and a
  // helper that calls useTransform is a rules-of-hooks violation waiting for
  // the first conditional.
  const islandX = useTransform(sx, [-0.5, 0.5], [3, -3]);
  const islandY = useTransform(sy, [-0.5, 0.5], [3, -3]);
  const composerX = useTransform(sx, [-0.5, 0.5], [2, -2]);
  const composerY = useTransform(sy, [-0.5, 0.5], [2, -2]);
  const threadX = useTransform(sx, [-0.5, 0.5], [1.4, -1.4]);
  const threadY = useTransform(sy, [-0.5, 0.5], [1.4, -1.4]);
  const bgX = useTransform(sx, [-0.5, 0.5], [0.6, -0.6]);
  const bgY = useTransform(sy, [-0.5, 0.5], [0.6, -0.6]);

  // Per-rail lighting. A single --rail-light brightened both sides together,
  // which is not what metal does: the rail turning toward the light picks up
  // the highlight while the opposite one rolls away into shadow. Driven off
  // the same sx that drives rotateY so the two can never disagree. The range
  // is deliberately tiny — this should be felt at the edge of vision, not
  // seen.
  const railL = useTransform(sx, [-0.5, 0, 0.5], [0.15, 0.5, 1]);
  const railR = useTransform(sx, [-0.5, 0, 0.5], [1, 0.5, 0.15]);
  // The glass's own cut edge, catching light as the panel turns. Polished,
  // not glowing: this rides the rotation, never the hover state, so it
  // behaves like an optical property rather than a highlight that switches
  // on.
  // T2.2 (A7) — this used to rebuild a linear-gradient string from the
  // rotation on every pointer frame, which repaints the glass-edge layer each
  // time. Two static gradients at the extremes of the same 115deg..65deg
  // sweep, cross-faded by the same sx, put the work on the compositor: the
  // angles, alphas and ranges are unchanged, only the mechanism is. The
  // component already uses this pattern for the two rails, for the same
  // reason a single gradient cannot animate its own stops.
  const edgeOpacityA = useTransform(sx, [-0.5, 0.5], [1, 0]);
  const edgeOpacityB = useTransform(sx, [-0.5, 0.5], [0, 1]);
  const edgeEngaged = useTransform(sEngaged, [0, 1], [0.7, 1]);
  // The shadow deepens and spreads as the device rises — a lift with a
  // constant shadow reads as the whole scene scaling, not as an object
  // leaving the surface.
  // Two shadows, not one. A real object resting on a surface has a tight,
  // dark contact shadow directly beneath it AND a wide soft ambient one; as
  // it lifts, the contact shadow fades and spreads while the ambient one
  // deepens. Animating only the ambient shadow is why the old lift read as
  // the whole scene scaling instead of an object leaving the surface.
  // T2.2 — the same two shadows, as two pre-blurred layers instead of one
  // box-shadow string rebuilt per frame. Blur is fixed at the midpoint of the
  // range each used to interpolate (ambient 40..68 -> 54, contact 10..22 ->
  // 16); opacity and y still travel their original ranges, both on the
  // compositor.
  const ambOpacity = useTransform(sEngaged, [0, 1], [0.42, 0.62]);
  const ambY = useTransform(sEngaged, [0, 1], [20, 36]);
  const contactOpacity = useTransform(sEngaged, [0, 1], [0.5, 0.26]);

  // The highlight sweeps opposite the tilt, which is what a reflection does:
  // the glass turns toward the light, so the bright band slides the other way.
  // Glare travel more than halved: 160% of the device width -> 60%. This was
  // the single most artificial thing in the interaction. A highlight that
  // crosses the entire face reads as a spotlight being dragged; a real
  // reflection of a fixed light source barely moves as you turn an object a
  // few degrees. It also no longer fades fully to zero at rest — glass is
  // never matte, and a highlight that appears out of nothing announces the
  // hover instead of rewarding it.
  // T2.2 — the centre used to move via --gx/--gy, repainting the radial every
  // frame. The layer is now 3x the device and carries a centred gradient of
  // the same relative size, translated instead: 78%..18% of the device width
  // is +-0.28W..-0.32W from centre, which on a 3W box is the percentages
  // below. Same travel, same size at any breakpoint, no repaint.
  const glareX = useTransform(sx, [-0.5, 0.5], ["9.33%", "-10.67%"]);
  const glareY = useTransform(sy, [-0.5, 0.5], ["7.33%", "-9.33%"]);
  const glareOpacity = useTransform(sEngaged, [0, 1], [0.35, 1]);
  // Edge lighting strengthens as the device turns into the light.
  const railLight = useTransform(sEngaged, [0, 1], [0, 1]);

  const handleMove = useCallback(
    (e: React.MouseEvent) => {
      const el = ref.current;
      if (!el || reducedMotion) return;
      const r = el.getBoundingClientRect();
      px.set((e.clientX - r.left) / r.width - 0.5);
      py.set((e.clientY - r.top) / r.height - 0.5);
    },
    [px, py, reducedMotion],
  );

  const setEngaged = useCallback(
    (on: boolean) => {
      if (reducedMotion) return;
      engaged.set(on ? 1 : 0);
      if (on) {
        // Entering is immediate: the raw value is set directly by pointer
        // move and the display spring does the smoothing.
        onEngagedChange?.(true);
        return;
      }
      // Leaving is not. Snapping the raw target to 0 made the device stop
      // being pushed the instant the cursor left, and the spring pulled it
      // straight home — correct, but weightless. Animating the raw target
      // home on its own soft spring, *underneath* the display spring, means
      // the device keeps travelling briefly in the direction it was already
      // going before it settles. Two springs in series, so momentum carries
      // and there is still no overshoot past centre: neither spring has any
      // bounce.
      const exit = { type: "spring", stiffness: 42, damping: 19, mass: 1.1 } as const;
      animate(px, 0, exit);
      animate(py, 0, exit);
      onEngagedChange?.(false);
    },
    [engaged, px, py, reducedMotion, onEngagedChange],
  );

  // prefers-reduced-motion gets the device with no interaction at all — not a
  // slower tilt. The request is less motion, and a 3D rotation is exactly the
  // vestibular trigger the media query exists to suppress.
  // Reduced motion loses the rotation, not the reflection. The brief is that
  // the glass always has a highlight — a surface that is matte at rest and
  // glossy on hover is not glass, and someone who asked for less motion has
  // not asked for a different material.
  if (reducedMotion) {
    return (
      <>
        {children(
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 z-20 bg-[radial-gradient(70%_55%_at_48%_47%,rgb(255_255_255/0.07),rgb(255_255_255/0.02)_45%,transparent_72%)]"
          />,
          undefined,
        )}
      </>
    );
  }

  const glare = (
    <m.div
      aria-hidden="true"
      style={{ opacity: glareOpacity, x: glareX, y: glareY }}
      className="pointer-events-none absolute -inset-[100%] z-20 bg-[radial-gradient(23.4%_18.3%_at_50%_50%,rgb(255_255_255/0.10),rgb(255_255_255/0.03)_45%,transparent_72%)]"
    />
  );

  return (
    // The perspective lives on the wrapper and the transform on the child:
    // putting both on one element makes the rotation flat and lifeless.
    <div style={{ perspective: 2200 }} className="w-full">
      <m.div
        ref={ref}
        // Mouse events, not pointer events. The tilt is a hover affordance
        // and hover does not exist on touch — pointer events would fire on a
        // tap and leave the device rotated with no way to un-rotate it.
        onMouseMove={handleMove}
        onMouseEnter={() => setEngaged(true)}
        onMouseLeave={() => setEngaged(false)}
        style={{
          rotateX,
          rotateY,
          y: lift,
          scale,
          transformStyle: "preserve-3d",
          borderRadius: "3.4rem",
          ["--rail-light" as string]: railLight,
        }}
        className="will-change-transform"
      >
        {/* The two shadow layers, behind the device and rotating with it. Each
            carries a static box-shadow; only opacity and y animate. */}
        <m.div
          aria-hidden="true"
          style={{ opacity: ambOpacity, y: ambY }}
          className="pointer-events-none absolute inset-0 -z-10 rounded-[3.4rem] shadow-[0_0_54px_-12px_rgb(0_0_0)]"
        />
        <m.div
          aria-hidden="true"
          style={{ opacity: contactOpacity }}
          className="pointer-events-none absolute inset-0 -z-10 rounded-[3.4rem] shadow-[0_6px_16px_-8px_rgb(0_0_0)]"
        />
        {children(glare, {
          railL: { opacity: railL },
          railR: { opacity: railR },
          glassEdgeA: { opacity: edgeOpacityA },
          glassEdgeB: { opacity: edgeOpacityB },
          glassEdgeEngaged: { opacity: edgeEngaged },
          island: { x: islandX, y: islandY },
          composer: { x: composerX, y: composerY },
          thread: { x: threadX, y: threadY },
          bg: { x: bgX, y: bgY },
        } as unknown as DeviceChrome)}
      </m.div>
    </div>
  );
}
