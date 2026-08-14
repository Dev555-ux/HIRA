import type { AnalyticsTrendPoint } from "@/lib/types";

const DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

// The API returns exactly one range's daily series — no prior-period
// baseline exists anywhere in the payload. This compares the back half of
// the fetched window against the front half, which is honest about what it
// is (movement within this period), not a claim about "vs last week".
export function periodTrendPct(points: AnalyticsTrendPoint[]): number | null {
  if (points.length < 4) return null; // too few points for a half-split to mean anything
  const mid = Math.floor(points.length / 2);
  const firstSum = points.slice(0, mid).reduce((sum, p) => sum + p.count, 0);
  const secondSum = points.slice(mid).reduce((sum, p) => sum + p.count, 0);
  if (firstSum === 0) return null;
  return Math.round(((secondSum - firstSum) / firstSum) * 100);
}

// Which day of week the series peaked on, averaged across however many
// occurrences of that weekday fall in the range (so a 30d/90d range doesn't
// just report whichever single day happened to be highest).
export function dayOfWeekPeak(points: AnalyticsTrendPoint[]): string | null {
  if (points.length === 0) return null;
  const sums = new Array(7).fill(0) as number[];
  const counts = new Array(7).fill(0) as number[];
  for (const p of points) {
    const dow = new Date(`${p.date}T00:00:00Z`).getUTCDay();
    sums[dow] += p.count;
    counts[dow] += 1;
  }
  let best = -1;
  let bestAvg = 0;
  for (let i = 0; i < 7; i++) {
    if (counts[i] === 0) continue;
    const avg = sums[i] / counts[i];
    if (avg > bestAvg) {
      bestAvg = avg;
      best = i;
    }
  }
  return best === -1 ? null : DAY_NAMES[best];
}
