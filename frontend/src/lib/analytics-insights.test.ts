import { describe, expect, it } from "vitest";
import { dayOfWeekPeak, periodTrendPct } from "./analytics-insights";

describe("periodTrendPct", () => {
  it("compares the back half of the window to the front half", () => {
    const points = [1, 1, 1, 1, 3, 3, 3, 3].map((count, i) => ({
      date: `2026-08-0${i + 1}`,
      count,
    }));
    // front half sums to 4, back half to 12 -> +200%
    expect(periodTrendPct(points)).toBe(200);
  });

  it("returns null rather than dividing by zero when the front half is empty", () => {
    const points = [0, 0, 0, 0, 1, 1, 1, 1].map((count, i) => ({
      date: `2026-08-0${i + 1}`,
      count,
    }));
    expect(periodTrendPct(points)).toBeNull();
  });

  it("returns null for a series too short to split meaningfully", () => {
    expect(periodTrendPct([{ date: "2026-08-01", count: 5 }])).toBeNull();
  });
});

describe("dayOfWeekPeak", () => {
  it("picks the weekday with the highest average, not just the single highest day", () => {
    // Two Mondays averaging 10, one Tuesday at 8 -> Monday wins on average
    // despite Tuesday's single occurrence being unremarkable either way.
    const points = [
      { date: "2026-08-03", count: 9 }, // Monday
      { date: "2026-08-04", count: 8 }, // Tuesday
      { date: "2026-08-10", count: 11 }, // Monday
    ];
    expect(dayOfWeekPeak(points)).toBe("Monday");
  });

  it("returns null for an empty series", () => {
    expect(dayOfWeekPeak([])).toBeNull();
  });
});
