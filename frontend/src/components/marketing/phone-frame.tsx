"use client";

import * as m from "motion/react-m";
import type { ReactNode } from "react";
import type { DeviceChrome } from "@/components/marketing/stage-parts";

// v0.69 — hardware pass. The PR-2 device read as "a phone" at a glance and
// fell apart on inspection: one flat body gradient, no side hardware, a
// cutout with nothing in it, and a bezel that shared an edge with the frame.
// Real hardware reads as real because of four things, and this adds all four.
//
//   1. A metal band, not a fill. A machined rail is brightest where it curves
//      away at the extreme left and right edges and darkest across the flat
//      of the side. That is a three-stop horizontal gradient, and it is the
//      single biggest tell — a flat grey body always looks like a drawing.
//   2. Nested radii. Body, rail, bezel and display each have their own corner
//      radius, decreasing inward. Sharing one radius across all four is what
//      makes a device look like a rounded rectangle with a picture in it.
//   3. Side hardware. Volume pair and an action button on the left, power on
//      the right, standing slightly proud of the rail with their own metal
//      gradient. Nobody looks at them directly; their absence is what gets
//      noticed.
//   4. Specular edges. A bright inset hairline along the top of the rail and
//      a dimmer one along the bottom — the light the rail catches, which is
//      the same treatment the glass material uses for the same reason.
//
// Deliberately generic: no manufacturer's exact island geometry, button
// placement, corner radius or icon set is reproduced. All chrome is
// aria-hidden; the conversation inside carries the meaning.

function StatusGlyphs() {
  return (
    <div className="flex items-center gap-1.5 text-foreground/75">
      <svg width="17" height="11" viewBox="0 0 17 11" fill="none" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => (
          <rect
            key={i}
            x={i * 4.5}
            y={8 - i * 2.4}
            width="2.6"
            height={3 + i * 2.4}
            rx="0.8"
            fill="currentColor"
            opacity={i === 3 ? 0.35 : 1}
          />
        ))}
      </svg>
      <svg width="15" height="11" viewBox="0 0 15 11" fill="none" aria-hidden="true">
        <path d="M1 4.1a9.4 9.4 0 0 1 13 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <path d="M3.6 6.7a5.7 5.7 0 0 1 7.8 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="7.5" cy="9.4" r="1.2" fill="currentColor" />
      </svg>
      <svg width="25" height="12" viewBox="0 0 25 12" fill="none" aria-hidden="true">
        <rect x="0.6" y="0.6" width="21" height="10.8" rx="3" stroke="currentColor" strokeWidth="1.1" opacity="0.45" />
        <rect x="2.2" y="2.2" width="15" height="7.6" rx="1.8" fill="currentColor" />
        <path d="M23.2 4.2v3.6a2 2 0 0 0 0-3.6Z" fill="currentColor" opacity="0.45" />
      </svg>
    </div>
  );
}

// A machined button: proud of the rail, lit on its outer face.
function SideButton({ className }: { className: string }) {
  return (
    <span
      aria-hidden="true"
      className={`absolute rounded-[2px] bg-[linear-gradient(180deg,oklch(0.55_0.01_70),oklch(0.38_0.008_70)_45%,oklch(0.3_0.006_70))] shadow-[0_1px_2px_rgb(0_0_0/0.45)] ${className}`}
    />
  );
}

export function PhoneFrame({
  children,
  time = "9:41",
  glare,
  chrome,
}: {
  children: ReactNode;
  time?: string;
  // Rendered above the screen content. The parent owns it because it tracks
  // the pointer, and this component is deliberately stateless.
  glare?: ReactNode;
  // Per-layer motion from DeviceShell: two rail lights, the glass edge, and
  // four display layers at different depths. Undefined under reduced motion,
  // where every layer simply stays put.
  chrome?: DeviceChrome;
}) {
  return (
    <div className="relative mx-auto w-full max-w-[350px]">
      {/* Side hardware sits behind the body so only the proud edge shows. */}
      {/* Refinement — proportions. The first pass drew buttons too long and
          too thick, which is what made them read as tabs stuck on the side.
          Real hardware: a short action button, a volume pair of equal length
          below it with a clear gap, and a longer power button set lower on
          the opposite side. 2.5px of visible thickness, not 3. */}
      <SideButton className="-left-[2px] top-[15.5%] h-[26px] w-[2.5px]" />
      <SideButton className="-left-[2px] top-[24%] h-[46px] w-[2.5px]" />
      <SideButton className="-left-[2px] top-[36%] h-[46px] w-[2.5px]" />
      <SideButton className="-right-[2px] top-[27%] h-[64px] w-[2.5px]" />

      {/* The rail. Bright at both extremes where the metal curves away,
          darkest across the flat of the side. */}
      <div className="relative rounded-[3.4rem] bg-[linear-gradient(90deg,oklch(0.62_0.012_70),oklch(0.34_0.008_70)_12%,oklch(0.28_0.006_70)_50%,oklch(0.34_0.008_70)_88%,oklch(0.62_0.012_70))] p-[3.5px] shadow-[0_2px_1px_rgb(255_255_255/0.12)_inset,0_-2px_1px_rgb(0_0_0/0.5)_inset]">
        {/* Refinement — the environment reflected in the rail. Polished metal
            does not just have edge highlights; it mirrors the room, which on
            a vertical rail shows as a brighter band around the horizon line
            and darker toward the ends. --rail-light is driven by the hover
            state, so the metal brightens as the device turns into the light.
            Pure decoration, inert to pointer and assistive tech. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 rounded-[3.4rem] bg-[linear-gradient(180deg,transparent,rgb(255_255_255/0.06)_18%,transparent_34%,transparent_62%,rgb(255_255_255/0.04)_78%,transparent)]"
        />
        {/* Micro-polish — the two rails light independently. The one turning
            toward the light picks up its highlight while the far one rolls
            away. Two narrow overlays rather than one gradient because the
            two sides have to animate against each other, which a single
            gradient's stops cannot do. Very low alpha on purpose: at rest
            both sit at half strength, so the hover reads as the highlight
            sliding across the metal rather than switching on. */}
        <m.div
          aria-hidden="true"
          style={chrome?.railL}
          className="pointer-events-none absolute inset-y-8 left-0 w-[7px] rounded-l-[3.4rem] bg-[linear-gradient(90deg,rgb(255_255_255/0.16),transparent)]"
        />
        <m.div
          aria-hidden="true"
          style={chrome?.railR}
          className="pointer-events-none absolute inset-y-8 right-0 w-[7px] rounded-r-[3.4rem] bg-[linear-gradient(270deg,rgb(255_255_255/0.16),transparent)]"
        />

        {/* Bezel — its own layer so the display's radius nests inside the
            rail's rather than sharing one edge. */}
        <div className="rounded-[3.2rem] bg-[oklch(0.11_0.004_60)] p-[8px]">
          <div className="relative isolate aspect-[9/16] overflow-hidden rounded-[2.7rem] bg-background shadow-[inset_0_1px_3px_rgb(0_0_0/0.6),inset_0_0_0_1px_rgb(255_255_255/0.045)]">
            {/* Glass thickness. A cover glass is a few millimetres deep, and
                what sells that is the bright hairline caught on its top cut
                edge with shadow pooling just under it. Without this the
                display looks printed onto the bezel rather than sunk beneath
                glass — the difference between a photograph and a render. */}
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 z-40 rounded-[2.7rem] shadow-[inset_0_1.5px_0_rgb(255_255_255/0.10),inset_0_-1px_0_rgb(255_255_255/0.04)]"
            />
            {/* The cut edge catching light as the panel turns. Driven by the
                rotation, not the hover state, so it behaves like an optical
                property of the glass rather than a highlight that switches on
                when a cursor arrives. */}
            <m.div
              aria-hidden="true"
              style={chrome?.glassEdge}
              className="pointer-events-none absolute inset-0 z-40 rounded-[2.7rem]"
            />
            {/* Deepest layer — the chat ground. Moves least of anything on
                the display, which is what makes the layers above it read as
                floating over it. */}
            <m.div
              aria-hidden="true"
              style={chrome?.bg}
              className="pointer-events-none absolute inset-[-4px] z-0 bg-background"
            />
            {/* Static sheen. The pointer-tracked glare is layered over this
                by the parent; this is the part that is always there. */}
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 z-20 bg-gradient-to-br from-foreground/[0.045] via-transparent to-transparent"
            />
            {glare}

            {/* Cutout, with an actual lens and a speaker slot in it. */}
            <m.div
              aria-hidden="true"
              style={chrome?.island}
              // Refinement — proportions. 88x27 was too small and too round
              // relative to the display; the cutout is ~32% of screen width
              // and noticeably wider than it is tall. The lens also shrinks:
              // at 8px it read as a decorative dot, and the catchlight is
              // what makes it a lens, not the size.
              className="absolute left-1/2 top-[10px] z-30 flex h-[30px] w-[106px] -translate-x-1/2 items-center justify-between rounded-full bg-[oklch(0.07_0.003_60)] px-3 shadow-[0_0_0_1px_rgb(255_255_255/0.035),inset_0_1px_1px_rgb(0_0_0/0.8)]"
            >
              {/* Earpiece slot — recessed, not a painted line. */}
              <span className="h-[3.5px] w-[22px] rounded-full bg-[oklch(0.04_0_0)] shadow-[inset_0_0.5px_0.5px_rgb(255_255_255/0.07)]" />
              <span className="relative size-[7px] rounded-full bg-[oklch(0.14_0.012_250)] ring-[0.5px] ring-foreground/[0.16]">
                <span className="absolute left-[1px] top-[1px] size-[2px] rounded-full bg-foreground/35" />
              </span>
            </m.div>

            <div
              aria-hidden="true"
              className="absolute inset-x-0 top-0 z-10 flex h-[46px] items-center justify-between px-7 text-[13px] font-semibold tabular-nums text-foreground/85"
            >
              <span>{time}</span>
              <StatusGlyphs />
            </div>

            <m.div style={chrome?.thread} className="relative z-10 flex h-full flex-col pb-6 pt-[46px]">
              {children}
            </m.div>

            <div
              aria-hidden="true"
              className="absolute bottom-2 left-1/2 z-20 h-[5px] w-[34%] -translate-x-1/2 rounded-full bg-foreground/25"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
