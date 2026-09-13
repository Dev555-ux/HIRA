"use client";

import { Check, Paperclip, Mic } from "lucide-react";
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
    <div className="animate-fade-in flex justify-start">
      <div className="max-w-[86%] rounded-2xl rounded-bl-md bg-muted px-3 py-2 shadow-e1">
        <p className="text-[13px] leading-snug">{text}</p>
        <Meta time={time} />
      </div>
    </div>
  );
}

export function ReplyBubble({ text, time }: { text: string; time: string }) {
  return (
    <div className="animate-fade-in flex justify-end">
      {/* bg-brand/20 + text-foreground, not the brand/brand-foreground pair:
          at 20% the fill is a tint over the screen, so the readable pairing
          is against the screen's own foreground. Measured, not assumed. */}
      <div className="max-w-[86%] rounded-2xl rounded-br-md bg-brand/20 px-3 py-2 shadow-e1 ring-1 ring-brand/25">
        <p className="text-[13px] leading-snug text-foreground">{text}</p>
        <Meta time={time} ticks />
      </div>
    </div>
  );
}

// The "HIRA is working" beat, shown in the conversation while the graph runs.
// Three dots is the one messaging convention worth keeping literally — it is
// universal, and inventing an alternative would cost comprehension for no
// gain. Purely decorative, and the stage is aria-hidden regardless.
export function TypingBubble() {
  return (
    <div className="animate-fade-in flex justify-end">
      <div className="flex items-center gap-1 rounded-2xl rounded-br-md bg-brand/12 px-3 py-2.5 ring-1 ring-brand/20">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="size-1.5 rounded-full bg-brand/70"
            style={{ animation: `typing-dot 1.2s ${i * 0.16}s ease-in-out infinite` }}
          />
        ))}
      </div>
    </div>
  );
}

// A composer bar. Inert by design — it is scenery inside an aria-hidden
// stage, so it is a <div>, never a real input a keyboard could land in.
export function Composer() {
  return (
    <div className="flex items-center gap-2 px-3.5 pt-2.5">
      <Paperclip className="size-4 shrink-0 text-muted-foreground/70" aria-hidden="true" />
      <div className="glass flex h-8 flex-1 items-center rounded-full border border-[color:var(--glass-border)] px-3">
        <span className="text-[12px] text-muted-foreground/70">Message</span>
      </div>
      <Mic className="size-4 shrink-0 text-muted-foreground/70" aria-hidden="true" />
    </div>
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
                strokeWidth={1.5}
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
        "transition-[border-color,background-color] duration-[var(--motion-slow)]",
        status === "idle" && "border-[color:var(--glass-border)]",
        status === "active" && "border-brand/80 bg-brand/[0.08]",
        status === "done" && "border-success/70 bg-success/[0.07]",
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
        <p
          className={cn(
            "truncate text-[11.5px] leading-tight transition-colors duration-[var(--motion-slow)]",
            status === "done" ? "text-success" : status === "active" ? "text-brand" : "text-muted-foreground",
          )}
        >
          {status === "idle" ? role : statusText}
        </p>
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
  children,
}: {
  status: Record<string, SystemStatus>;
  hubState: "idle" | "working" | "success";
  settled: boolean;
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
      <div className="hidden lg:block">
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
        <div className="glass rounded-2xl border border-[color:var(--glass-border)] p-2 shadow-e3">
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
