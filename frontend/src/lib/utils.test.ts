import { describe, expect, it } from "vitest";
import { cn, formatRelativeTime } from "./utils";

describe("cn", () => {
  it("merges class names and dedupes conflicting tailwind utilities", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
    expect(cn("text-sm", false && "hidden", "font-medium")).toBe(
      "text-sm font-medium",
    );
  });
});

describe("formatRelativeTime", () => {
  it("returns 'just now' for the current time", () => {
    expect(formatRelativeTime(new Date().toISOString())).toBe("just now");
  });

  it("formats minutes and hours", () => {
    const tenMinAgo = new Date(Date.now() - 10 * 60_000).toISOString();
    expect(formatRelativeTime(tenMinAgo)).toBe("10m ago");
    const twoHoursAgo = new Date(Date.now() - 2 * 3_600_000).toISOString();
    expect(formatRelativeTime(twoHoursAgo)).toBe("2h ago");
  });

  it("returns empty string for invalid input", () => {
    expect(formatRelativeTime("not-a-date")).toBe("");
  });
});
