"use client";

import { useId, useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import type { ActivityState } from "@/components/ui/activity-dot";

// ActivityState -> a real color value (not a Tailwind class) for use inside
// an SVG gradient stop. Same semantic mapping as ActivityDot's dotColor —
// duplicated here only because gradient stops need a CSS value, not a
// class name. Tokens already include their own hsl(...) wrapper (see
// globals.css), so referenced raw via var() — no extra hsl() wrapping,
// unlike TrendChart's existing (invalid, falls back to black) `hsl(var(--primary))`.
const STATE_COLOR: Record<ActivityState, string> = {
  idle: "var(--muted-foreground)",
  working: "var(--foreground)",
  waiting: "var(--warning)",
  success: "var(--success)",
  error: "var(--destructive)",
};

export interface DonutSegment {
  key: string;
  label: string;
  value: number;
  state: ActivityState;
}

// Soft-depth 2D donut — a radial gradient per slice plus a drop-shadow on
// the whole chart, not literal 3D (perspective distorts slice area/angle
// and never actually improves comprehension — see Sprint 84.3 design
// review). Used only for genuine part-to-whole state breakdowns (≤6
// segments): conversation status, appointment status.
export function DonutChart({ title, segments }: { title: string; segments: DonutSegment[] }) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const gradId = useId();
  const total = segments.reduce((sum, s) => sum + s.value, 0);

  const summary =
    total === 0
      ? `${title}: no data.`
      : `${title}: ${segments
          .map((s) => `${s.label} ${s.value} (${Math.round((s.value / total) * 100)}%)`)
          .join(", ")}. Total ${total}.`;

  return (
    <div>
      <div className="flex items-center gap-5" role="img" aria-label={summary}>
        <div className="relative size-[136px] shrink-0" style={{ filter: "drop-shadow(0 6px 14px rgb(0 0 0 / 0.12))" }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <defs>
                {segments.map((s, i) => (
                  <radialGradient key={s.key} id={`${gradId}-${i}`} cx="35%" cy="30%" r="75%">
                    <stop offset="0%" stopColor={STATE_COLOR[s.state]} stopOpacity={1} />
                    <stop offset="100%" stopColor={STATE_COLOR[s.state]} stopOpacity={0.72} />
                  </radialGradient>
                ))}
              </defs>
              <Pie
                data={segments}
                dataKey="value"
                nameKey="label"
                innerRadius="62%"
                outerRadius="92%"
                startAngle={90}
                endAngle={-270}
                paddingAngle={segments.length > 1 ? 2 : 0}
                stroke="none"
                isAnimationActive={false}
                onMouseEnter={(_, index) => setActiveIndex(index)}
                onMouseLeave={() => setActiveIndex(null)}
              >
                {segments.map((s, i) => (
                  <Cell
                    key={s.key}
                    fill={`url(#${gradId}-${i})`}
                    opacity={activeIndex === null || activeIndex === i ? 1 : 0.32}
                  />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <div className="text-xl font-semibold tabular-nums tracking-tight">{total}</div>
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">total</div>
          </div>
        </div>
        <ul className="flex-1 space-y-1">
          {segments.map((s, i) => {
            const pct = total > 0 ? Math.round((s.value / total) * 100) : 0;
            return (
              <li
                key={s.key}
                className="-ml-1 flex items-center gap-2 rounded-md px-1 py-1 text-sm transition-colors hover:bg-muted"
                onMouseEnter={() => setActiveIndex(i)}
                onMouseLeave={() => setActiveIndex(null)}
              >
                <span
                  className="size-2 shrink-0 rounded-full"
                  style={{ background: STATE_COLOR[s.state] }}
                />
                <span className="flex-1 font-medium">{s.label}</span>
                <span className="text-xs tabular-nums text-muted-foreground">
                  {s.value} · {pct}%
                </span>
              </li>
            );
          })}
        </ul>
      </div>
      <details className="mt-2">
        <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
          View as table
        </summary>
        <div className="mt-2 max-h-48 overflow-y-auto rounded-md border">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-muted/50">
              <tr>
                <th className="px-2 py-1 text-left font-medium">Status</th>
                <th className="px-2 py-1 text-right font-medium">Count</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {segments.map((s) => (
                <tr key={s.key}>
                  <td className="px-2 py-1">{s.label}</td>
                  <td className="px-2 py-1 text-right tabular-nums">{s.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
