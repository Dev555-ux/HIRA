"use client";

import type { LucideIcon } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
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

// Sprint 87 — brought up to the same premium mark language as TrendChart
// (gradient area fill, endpoint glow + marker) rather than the bare stroked
// line this used to be, without adopting TrendChart itself: that component's
// hover tooltip, axis labels, and "view as table" fallback are sized for a
// dedicated chart card, and dropping its 148px-tall default variant into a
// compact KPI tile would blow the tile's height out past its siblings.
function MiniSparkline({ data, height = 32 }: { data: AnalyticsTrendPoint[]; height?: number }) {
  const w = 200;
  const h = height;
  const gradientId = useId();
  const counts = data.map((d) => d.count);
  const max = Math.max(1, ...counts);
  const points = data.map((d, i) => ({
    x: data.length > 1 ? (i / (data.length - 1)) * w : w,
    y: h - 2 - (d.count / max) * (h - 6),
  }));
  const d = buildSmoothPath(points);
  const areaPath = points.length > 0 ? `${d} L${w},${h} L0,${h} Z` : "";
  const last = points[points.length - 1];
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      width="100%"
      height={h}
      preserveAspectRatio="none"
      className="overflow-visible"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.18" />
          <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
        </linearGradient>
      </defs>
      {points.length > 0 && <path d={areaPath} fill={`url(#${gradientId})`} />}
      <path d={d} fill="none" stroke="var(--primary)" strokeWidth="2" strokeLinecap="round" opacity="0.9" />
      {last && (
        <>
          <circle cx={last.x} cy={last.y} r={h >= 48 ? 7 : 5} className="fill-primary" opacity="0.16" />
          <circle cx={last.x} cy={last.y} r={h >= 48 ? 3 : 2.25} className="fill-card stroke-primary" strokeWidth="1.75" />
        </>
      )}
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
  className,
  size,
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
  className?: string;
  /** Sprint 87 — an explicit, opt-in size tier so one KPI can read as a
   *  row's headline and others as quieter supporting detail, without
   *  changing this component's default rendering for its other callers
   *  (Analytics, Ops, AiMetricsSection all render plain `<StatCard>` with
   *  no `size` and must stay pixel-identical to before this sprint).
   *  `"default"` is exactly the pre-Sprint-87 look. `"featured"` is the one
   *  headline tile in a row — bigger number, bigger chart, brand-tinted icon
   *  chip. `"compact"` is a `secondary`-elevation supporting tile — smaller
   *  number, tighter padding. */
  size?: "default" | "featured" | "compact";
}) {
  const animated = useCountUp(countTo ?? null);
  const isFeatured = size === "featured";
  const isCompact = size === "compact";

  return (
    <Card interactive variant={isCompact ? "secondary" : "primary"} className={cn("group", className)}>
      <CardContent className={cn("p-6", isFeatured && "sm:p-7", isCompact && "p-5")}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            {loading ? (
              <Skeleton className={isFeatured ? "h-11 w-20" : isCompact ? "h-7 w-14" : "h-9 w-16"} />
            ) : (
              <p
                className={cn(
                  "animate-fade-in font-semibold tabular-nums tracking-tight",
                  isFeatured ? "text-4xl sm:text-5xl" : isCompact ? "text-2xl" : "text-3xl",
                )}
              >
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
            <p className={cn("text-muted-foreground", isFeatured ? "mt-2 text-sm" : isCompact ? "mt-1 text-xs" : "mt-1.5 text-sm")}>
              {label}
            </p>
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
              "flex shrink-0 items-center justify-center rounded-full transition-colors duration-200",
              isFeatured ? "size-11" : isCompact ? "size-8" : "size-9",
              tone === "warning"
                ? "bg-warning/12 group-hover:bg-warning/18"
                : isFeatured
                  ? "bg-brand/10 group-hover:bg-brand/15"
                  : "bg-primary/10 group-hover:bg-primary/15",
            )}
          >
            <Icon
              className={cn(
                isFeatured ? "size-5" : isCompact ? "size-3.5" : "size-4",
                tone === "warning" ? "text-warning" : isFeatured ? "text-brand" : "text-primary",
              )}
            />
          </div>
        </div>
        {sparkline && sparkline.length > 1 && (
          <div className={isFeatured ? "mt-4 h-14" : "mt-3 h-8"}>
            <MiniSparkline data={sparkline} height={isFeatured ? 56 : 32} />
          </div>
        )}
        {hint && <p className="mt-3 text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}
