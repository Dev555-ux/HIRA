"use client";

import { useId, useState } from "react";

export interface TrendPoint {
  date: string;
  count: number;
}

const WIDTH = 320;
const HEIGHT = 128;
// Top strip reserved so the endpoint value badge never clips the card edge —
// data plots into [TOP_MARGIN, HEIGHT - BOTTOM_MARGIN], not the full height.
const TOP_MARGIN = 28;
const BOTTOM_MARGIN = 8;

function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

// Hand-rolled per DESIGN-SCREENBOOK-002 §10 (a charting library was
// explicitly out of scope for M14) and the dataviz skill's mark spec: a
// single sequential-hue line (magnitude over time, not identity — no
// categorical palette needed), one baseline gridline, rounded caps, an
// emphasized endpoint, and a real hover tooltip rather than a bare dot.
// Uses --primary (the same tone StatCard's own KPI icons already use on
// this page), not --brand — Cobalt is reserved for AI-authored content
// (M4), and conversation/message/lead/appointment volume isn't that.
//
// Sprint 84.3: grew from a 72px sparkline to a proper 128px chart with a
// date axis and a permanent endpoint value badge (borrowed from a Dribbble
// reference's "label the mark directly, don't make hover mandatory"
// principle) — the hover crosshair below is additive detail, not the only
// way to read the latest value. Also fixes a latent bug: the gradient fill
// used `hsl(var(--primary))`, but --primary already includes its own
// hsl(...) wrapper in globals.css, so that nested call was invalid CSS and
// silently fell back to stop-color's initial value (black) in both themes.
export function TrendChart({ title, data }: { title: string; data: TrendPoint[] }) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const gradientId = useId();

  const counts = data.map((d) => d.count);
  const max = Math.max(1, ...counts);
  const total = counts.reduce((a, b) => a + b, 0);
  const plotHeight = HEIGHT - TOP_MARGIN - BOTTOM_MARGIN;

  const points = data.map((d, i) => {
    const x = data.length > 1 ? (i / (data.length - 1)) * WIDTH : WIDTH;
    const y = HEIGHT - BOTTOM_MARGIN - (d.count / max) * plotHeight;
    return { x, y, ...d };
  });

  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");
  const areaPath = `${linePath} L${WIDTH},${HEIGHT} L0,${HEIGHT} Z`;
  const hovered = hoverIndex !== null ? points[hoverIndex] : null;
  const last = points[points.length - 1];

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
              <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.16" />
              <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
            </linearGradient>
          </defs>
          <line x1="0" y1={HEIGHT} x2={WIDTH} y2={HEIGHT} className="stroke-border" strokeWidth="1" />
          {points.length > 0 && (
            <>
              <path d={areaPath} fill={`url(#${gradientId})`} />
              <path
                d={linePath}
                fill="none"
                className="stroke-primary"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <circle cx={last.x} cy={last.y} r="3.5" className="fill-card stroke-primary" strokeWidth="2" />
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
                  <circle cx={hovered.x} cy={hovered.y} r="3.5" className="fill-card stroke-primary" strokeWidth="2" />
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
      </div>
      {data.length > 0 && (
        <div className="mt-1 flex items-center justify-between type-caption text-muted-foreground">
          <span>{formatDate(data[0].date)}</span>
          {data.length > 2 && <span>{formatDate(data[Math.floor((data.length - 1) / 2)].date)}</span>}
          <span>{formatDate(data[data.length - 1].date)}</span>
        </div>
      )}
      {hovered && (
        <div className="mt-1 flex items-center justify-between type-caption text-muted-foreground">
          <span>{formatDate(hovered.date)}</span>
          <span className="font-medium text-foreground tabular-nums">{hovered.count}</span>
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
