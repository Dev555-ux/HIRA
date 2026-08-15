"use client";

import type { LucideIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { buildSmoothPath } from "@/components/ui/trend-chart";
import type { AnalyticsTrendPoint } from "@/lib/types";
import { cn } from "@/lib/utils";

// Counts up FROM the previous value whenever target genuinely changes (e.g.
// a 30d -> 7d range toggle) — not from zero on first mount, where there's no
// "previous" value for a count-up to mean anything, and where it would just
// delay a screen reader / test / first paint from seeing the real number.
// displayRef (not the `value` state) is what animation frames read as the
// starting point, so this only depends on `target`.
function useCountUp(target: number | null): number {
  const [value, setValue] = useState(target ?? 0);
  const displayRef = useRef(target ?? 0);
  const mountedTarget = useRef<number | null>(null);

  useEffect(() => {
    if (target === null) return;
    if (mountedTarget.current === null) {
      mountedTarget.current = target;
      displayRef.current = target;
      setValue(target);
      return;
    }
    if (mountedTarget.current === target) return;
    mountedTarget.current = target;

    const reduceMotion =
      typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) {
      displayRef.current = target;
      setValue(target);
      return;
    }

    const from = displayRef.current;
    const to = target; // narrowed local — `target` itself loses its null-check narrowing inside the nested tick()
    const duration = 600;
    const start = performance.now();
    let frame: number;
    function tick(now: number) {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - (1 - progress) ** 3; // ease-out-cubic
      const next = Math.round(from + (to - from) * eased);
      displayRef.current = next;
      setValue(next);
      if (progress < 1) frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target]);

  return value;
}

function MiniSparkline({ data }: { data: AnalyticsTrendPoint[] }) {
  const w = 200;
  const h = 32;
  const counts = data.map((d) => d.count);
  const max = Math.max(1, ...counts);
  const points = data.map((d, i) => ({
    x: data.length > 1 ? (i / (data.length - 1)) * w : w,
    y: h - 2 - (d.count / max) * (h - 6),
  }));
  const d = buildSmoothPath(points);
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      width="100%"
      height={h}
      preserveAspectRatio="none"
      className="overflow-visible"
      aria-hidden="true"
    >
      <path d={d} fill="none" stroke="var(--primary)" strokeWidth="1.75" strokeLinecap="round" opacity="0.85" />
    </svg>
  );
}

export function StatCard({
  label,
  value,
  icon: Icon,
  hint,
  loading,
  period,
  delta,
  countTo,
  prefix,
  suffix,
  sparkline,
  tone = "neutral",
}: {
  label: string;
  value: React.ReactNode;
  icon: LucideIcon;
  hint?: string;
  loading?: boolean;
  /** Explicit time window, e.g. "Last 30 Days" — KPIs should never leave the window ambiguous. */
  period?: string;
  /** Real delta only — omit entirely rather than fabricate one for metrics with no prior-period baseline. */
  delta?: { pct: number; direction: "up" | "down" } | null;
  /** When set, animates the displayed number from 0 to this value instead of rendering `value` statically. */
  countTo?: number;
  /** Rendered before the animated number, e.g. "≈" — only applies when `countTo` is set. */
  prefix?: string;
  /** Rendered after the animated number, e.g. "%" or "h" — only applies when `countTo` is set. */
  suffix?: string;
  /** Optional real daily series for a mini trend line under the number. */
  sparkline?: AnalyticsTrendPoint[];
  /** "warning" tints the icon chip for metrics that are a caution signal, not a plain volume metric. */
  tone?: "neutral" | "warning";
}) {
  const animated = useCountUp(countTo ?? null);

  return (
    <Card interactive className="group">
      <CardContent className="p-6">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            {loading ? (
              <Skeleton className="h-9 w-16" />
            ) : (
              <p className="animate-fade-in text-3xl font-semibold tabular-nums tracking-tight">
                {countTo !== undefined ? (
                  <>
                    {prefix}
                    {animated.toLocaleString()}
                    {suffix}
                  </>
                ) : (
                  value
                )}
              </p>
            )}
            <p className="mt-1.5 text-sm text-muted-foreground">{label}</p>
            {(period ?? delta) && (
              <div className="mt-1.5 flex items-center gap-2 type-caption">
                {delta && (
                  <span
                    className={cn(
                      "font-semibold",
                      delta.direction === "up" ? "text-success" : "text-muted-foreground",
                    )}
                  >
                    {delta.direction === "up" ? "↑" : "↓"} {Math.abs(delta.pct)}%
                  </span>
                )}
                {period && <span className="text-muted-foreground">{period}</span>}
              </div>
            )}
          </div>
          <div
            className={cn(
              "flex size-9 shrink-0 items-center justify-center rounded-full transition-colors duration-200",
              tone === "warning" ? "bg-warning/12 group-hover:bg-warning/18" : "bg-primary/10 group-hover:bg-primary/15",
            )}
          >
            <Icon className={cn("size-4", tone === "warning" ? "text-warning" : "text-primary")} />
          </div>
        </div>
        {sparkline && sparkline.length > 1 && (
          <div className="mt-3 h-8">
            <MiniSparkline data={sparkline} />
          </div>
        )}
        {hint && <p className="mt-3 text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}
