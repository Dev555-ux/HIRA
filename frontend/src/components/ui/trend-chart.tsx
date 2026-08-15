"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";

export interface TrendPoint {
  date: string;
  count: number;
}

type Variant = "default" | "hero";

// Two canvases: the everyday card size, and the Hero Conversation Trend's
// dominant size (Sprint 85). Same component, same math — only the geometry
// constants change, so the hero doesn't drift from the small cards' behavior.
const SIZE: Record<Variant, { width: number; height: number; topMargin: number; bottomMargin: number }> = {
  default: { width: 320, height: 148, topMargin: 30, bottomMargin: 8 },
  hero: { width: 960, height: 300, topMargin: 44, bottomMargin: 12 },
};

function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

// Catmull-Rom -> cubic Bezier: a smooth curve that still passes exactly
// through every real data point (unlike a fitted/approximating curve), so
// the hover crosshair and endpoint marker stay pixel-accurate to the real
// value at that point. Exported so StatCard's KPI sparklines reuse the exact
// same curve math instead of a second, slightly different implementation.
export function buildSmoothPath(points: { x: number; y: number }[]): string {
  if (points.length === 0) return "";
  if (points.length === 1) return `M${points[0].x},${points[0].y}`;
  let d = `M${points[0].x},${points[0].y}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(i - 1, 0)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(i + 2, points.length - 1)];
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C${c1x},${c1y} ${c2x},${c2y} ${p2.x},${p2.y}`;
  }
  return d;
}

// Hand-rolled per DESIGN-SCREENBOOK-002 §10 (a charting library was
// explicitly out of scope for M14) and the dataviz skill's mark spec: a
// single sequential-hue line (magnitude over time, not identity — no
// categorical palette needed), rounded caps, an emphasized endpoint, and a
// real hover tooltip rather than a bare dot. Uses --primary (the same tone
// StatCard's own KPI icons already use on this page), not --brand — Cobalt
// is reserved for AI-authored content (M4), and conversation/message/lead/
// appointment volume isn't that.
//
// Sprint 85 (Premium Analytics Redesign): kept the hand-rolled approach
// rather than migrating to Recharts (see Sprint 85 architecture decision) —
// added bezier smoothing, an endpoint glow, a floating hover tooltip, an
// "elegant grid," and a `variant="hero"` size + one-time draw-in animation
// for the Conversation Trend centerpiece. All additive to the existing
// accessible summary / hover crosshair / "View as table" fallback below.
export function TrendChart({
  title,
  data,
  variant = "default",
}: {
  title: string;
  data: TrendPoint[];
  variant?: Variant;
}) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const gradientId = useId();
  const pathRef = useRef<SVGPathElement>(null);
  const { width: WIDTH, height: HEIGHT, topMargin: TOP_MARGIN, bottomMargin: BOTTOM_MARGIN } = SIZE[variant];

  const { points, linePath, areaPath, max, total } = useMemo(() => {
    const counts = data.map((d) => d.count);
    const max = Math.max(1, ...counts);
    const total = counts.reduce((a, b) => a + b, 0);
    const plotHeight = HEIGHT - TOP_MARGIN - BOTTOM_MARGIN;
    const points = data.map((d, i) => {
      const x = data.length > 1 ? (i / (data.length - 1)) * WIDTH : WIDTH;
      const y = HEIGHT - BOTTOM_MARGIN - (d.count / max) * plotHeight;
      return { x, y, ...d };
    });
    const linePath = buildSmoothPath(points);
    const areaPath = points.length > 0 ? `${linePath} L${WIDTH},${HEIGHT} L0,${HEIGHT} Z` : "";
    return { points, linePath, areaPath, max, total };
  }, [data, WIDTH, HEIGHT, TOP_MARGIN, BOTTOM_MARGIN]);

  const hovered = hoverIndex !== null ? points[hoverIndex] : null;
  const last = points[points.length - 1];

  // One-time draw-in for the hero chart only — the small cards stay static
  // so four simultaneous draw animations don't compete for attention with
  // the one that's supposed to be the page's focal point. The global
  // reduced-motion guard in globals.css forces transition-duration to
  // 0.01ms, so this collapses to an instant reveal automatically.
  useEffect(() => {
    if (variant !== "hero" || !pathRef.current || points.length < 2) return;
    const el = pathRef.current;
    // getTotalLength() isn't implemented in every SVG DOM (notably jsdom, used
    // by this project's own test suite) — skip the draw-in rather than throw;
    // the line still renders fully, just without the animated reveal.
    if (typeof el.getTotalLength !== "function") return;
    const length = el.getTotalLength();
    el.style.transition = "none";
    el.style.strokeDasharray = `${length}`;
    el.style.strokeDashoffset = `${length}`;
    el.getBoundingClientRect(); // force reflow before re-enabling the transition
    el.style.transition = "stroke-dashoffset 1100ms var(--ease-out-quart)";
    const frame = requestAnimationFrame(() => {
      el.style.strokeDashoffset = "0";
    });
    return () => cancelAnimationFrame(frame);
  }, [linePath, variant, points.length]);

  function handleMove(e: React.PointerEvent<SVGRectElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    const index = Math.round(ratio * (points.length - 1));
    setHoverIndex(Math.min(points.length - 1, Math.max(0, index)));
  }

  const summary =
    data.length === 0
      ? `${title}: no data.`
      : `${title}: ${total} total from ${formatDate(data[0].date)} to ${formatDate(data[data.length - 1].date)}, peak ${max} on a single day.`;

  const glowRadius = variant === "hero" ? 13 : 8;
  const endpointRadius = variant === "hero" ? 5 : 3.5;

  return (
    <div>
      <div className="relative">
        <svg
          role="img"
          aria-label={summary}
          width="100%"
          height={HEIGHT}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          preserveAspectRatio="none"
          className="overflow-visible"
        >
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--primary)" stopOpacity={variant === "hero" ? 0.22 : 0.16} />
              <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
            </linearGradient>
          </defs>
          {/* Elegant grid — three faint interior lines plus the baseline, replacing the old single bottom rule. */}
          {[0.25, 0.5, 0.75].map((f) => (
            <line
              key={f}
              x1="0"
              y1={TOP_MARGIN + (HEIGHT - TOP_MARGIN - BOTTOM_MARGIN) * f}
              x2={WIDTH}
              y2={TOP_MARGIN + (HEIGHT - TOP_MARGIN - BOTTOM_MARGIN) * f}
              className="stroke-border"
              strokeWidth="1"
              opacity="0.5"
            />
          ))}
          <line x1="0" y1={HEIGHT} x2={WIDTH} y2={HEIGHT} className="stroke-border" strokeWidth="1" />
          {points.length > 0 && (
            <>
              <path d={areaPath} fill={`url(#${gradientId})`} />
              <path
                ref={pathRef}
                d={linePath}
                fill="none"
                className="stroke-primary"
                strokeWidth={variant === "hero" ? 2.5 : 2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              {/* Endpoint glow — a soft, low-opacity halo behind the solid marker. No blur filter, just a larger translucent circle underneath. */}
              <circle cx={last.x} cy={last.y} r={glowRadius} className="fill-primary" opacity="0.16" />
              <circle
                cx={last.x}
                cy={last.y}
                r={endpointRadius}
                className="fill-card stroke-primary"
                strokeWidth="2"
              />
              {hovered && (
                <>
                  <line
                    x1={hovered.x}
                    y1={TOP_MARGIN}
                    x2={hovered.x}
                    y2={HEIGHT}
                    className="stroke-border"
                    strokeWidth="1"
                    strokeDasharray="2,2"
                  />
                  <circle cx={hovered.x} cy={hovered.y} r={endpointRadius} className="fill-card stroke-primary" strokeWidth="2" />
                </>
              )}
              {/* Pointer-capture overlay — invisible, sits above the visible marks. */}
              <rect
                x="0"
                y="0"
                width={WIDTH}
                height={HEIGHT}
                fill="transparent"
                onPointerMove={handleMove}
                onPointerLeave={() => setHoverIndex(null)}
              />
            </>
          )}
        </svg>
        {points.length > 0 && (
          <div
            className="pointer-events-none absolute rounded-md bg-foreground px-1.5 py-0.5 text-[10px] font-semibold tabular-nums text-background"
            style={{
              left: `${(last.x / WIDTH) * 100}%`,
              top: `${(last.y / HEIGHT) * 100}%`,
              transform: "translate(-50%, -135%)",
            }}
          >
            {last.count}
          </div>
        )}
        {/* Refined floating tooltip — replaces the old below-chart hover row so the value reads right where the cursor is. */}
        {hovered && (
          <div
            className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-md border bg-popover px-2.5 py-1.5 text-xs shadow-e3"
            style={{
              left: `${(hovered.x / WIDTH) * 100}%`,
              top: `${Math.max(0, (hovered.y / HEIGHT) * 100 - 6)}%`,
            }}
          >
            <span className="text-muted-foreground">{formatDate(hovered.date)}</span>{" "}
            <span className="font-semibold tabular-nums">{hovered.count}</span>
          </div>
        )}
      </div>
      {data.length > 0 && (
        <div className="mt-1.5 flex items-center justify-between type-caption text-muted-foreground">
          <span>{formatDate(data[0].date)}</span>
          {data.length > 2 && <span>{formatDate(data[Math.floor((data.length - 1) / 2)].date)}</span>}
          <span>{formatDate(data[data.length - 1].date)}</span>
        </div>
      )}
      <details className="mt-2">
        <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
          View as table
        </summary>
        <div className="mt-2 max-h-48 overflow-y-auto rounded-md border">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-muted/50">
              <tr>
                <th className="px-2 py-1 text-left font-medium">Date</th>
                <th className="px-2 py-1 text-right font-medium">Count</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.map((d) => (
                <tr key={d.date}>
                  <td className="px-2 py-1">{formatDate(d.date)}</td>
                  <td className="px-2 py-1 text-right tabular-nums">{d.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
