import type { ReactNode } from "react";

// PR-2 — presentation only. Still no state, no effects, no animation: a
// static device around whatever it's given.
//
// What changed from the Sprint 66 version: that frame was a rounded
// rectangle with a speaker slot and two grey dots, and at any size it read
// as a placeholder rather than a phone. Three things make a device read as
// real, and none of them is detail for its own sake:
//
//   1. Proportion. A phone is ~19.5:9, not a squarish card. The aspect ratio
//      is now enforced on the screen so the frame cannot drift as content
//      changes height — which is also what stops the stage jumping between
//      beats.
//   2. A layered edge. Real hardware has an outer body, a bright chamfer
//      catching light, and a black bezel before the display starts. Three
//      1px-ish layers, not one border.
//   3. The cutout and status bar. A camera housing and a signal/battery
//      readout are the two things the eye checks without being asked.
//
// Deliberately generic hardware: no manufacturer's exact island geometry,
// corner radius or icon set is reproduced, and the status glyphs are drawn
// as plain bars rather than any platform's. All chrome is aria-hidden — the
// conversation inside carries the meaning, and assistive tech reaches
// straight through to it.
//
// Colours come from tokens, so inside the hero's dark scope the device reads
// as dark hardware and in a light context as light hardware, with no
// per-theme branch here.

// A carrier/wifi/battery readout drawn as geometry rather than icons: the
// point is the *silhouette* the eye recognises, and plain bars carry that
// without reproducing any platform's icon set.
function StatusGlyphs() {
  return (
    <div className="flex items-center gap-1.5 text-foreground/70">
      {/* Signal — four ascending bars */}
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
      {/* Wifi — three arcs */}
      <svg width="15" height="11" viewBox="0 0 15 11" fill="none" aria-hidden="true">
        <path d="M1 4.1a9.4 9.4 0 0 1 13 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <path d="M3.6 6.7a5.7 5.7 0 0 1 7.8 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="7.5" cy="9.4" r="1.2" fill="currentColor" />
      </svg>
      {/* Battery */}
      <svg width="25" height="12" viewBox="0 0 25 12" fill="none" aria-hidden="true">
        <rect x="0.6" y="0.6" width="21" height="10.8" rx="3" stroke="currentColor" strokeWidth="1.1" opacity="0.45" />
        <rect x="2.2" y="2.2" width="15" height="7.6" rx="1.8" fill="currentColor" />
        <path d="M23.2 4.2v3.6a2 2 0 0 0 0-3.6Z" fill="currentColor" opacity="0.45" />
      </svg>
    </div>
  );
}

export function PhoneFrame({ children, time = "9:41" }: { children: ReactNode; time?: string }) {
  return (
    // Outer body. The gradient is the light falling down the metal; the ring
    // is the chamfer. shadow-e5 (not e3) because the device is now the
    // heaviest object on the stage and has to sit above the graph beside it.
    <div className="relative mx-auto w-full max-w-[360px] rounded-[3.2rem] bg-gradient-to-b from-foreground/[0.14] to-foreground/[0.06] p-[3px] shadow-e5 ring-1 ring-inset ring-foreground/15">
      {/* Bezel — the black band between body and display. Its own layer so
          the display's corner radius nests inside the body's rather than
          sharing one edge, which is the tell that separates a device from a
          rounded rectangle. */}
      <div className="rounded-[3.05rem] bg-[oklch(0.14_0.006_60)] p-[9px]">
        {/* 9:16, not a literal 9:19.5. A real handset's proportions left
            ~500px of empty screen above a two-message thread, and a hero is
            not improved by an accurate void. This is still unmistakably a
            phone and it lets the conversation fill the glass. */}
        <div className="relative isolate aspect-[9/16] overflow-hidden rounded-[2.5rem] bg-background">
          {/* Screen sheen — a single diagonal highlight across the glass.
              pointer-events-none and above the content, low enough not to
              touch legibility (verified by the contrast pass, not assumed). */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 z-20 bg-gradient-to-br from-foreground/[0.05] via-transparent to-transparent"
          />

          {/* Camera housing. A pill, floating over the content the way a
              real cutout does, with a faint lens. */}
          <div
            aria-hidden="true"
            className="absolute left-1/2 top-2.5 z-20 flex h-[26px] w-[86px] -translate-x-1/2 items-center justify-end rounded-full bg-[oklch(0.12_0.006_60)] pr-2.5"
          >
            <span className="size-[7px] rounded-full bg-foreground/20 ring-1 ring-foreground/10" />
          </div>

          {/* Status bar — sits level with the cutout, split around it. */}
          <div
            aria-hidden="true"
            className="absolute inset-x-0 top-0 z-10 flex h-[46px] items-center justify-between px-6 text-[13px] font-semibold tabular-nums text-foreground/80"
          >
            <span>{time}</span>
            <StatusGlyphs />
          </div>

          {/* Content sits below the status bar and above the home indicator. */}
          <div className="flex h-full flex-col pb-6 pt-[46px]">{children}</div>

          {/* Home indicator */}
          <div
            aria-hidden="true"
            className="absolute bottom-2 left-1/2 z-20 h-[5px] w-[36%] -translate-x-1/2 rounded-full bg-foreground/25"
          />
        </div>
      </div>
    </div>
  );
}
