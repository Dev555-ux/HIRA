import { describe, expect, it } from "vitest";
import {
  cn,
  describeWhatsAppConnection,
  formatRelativeTime,
  toDateInputValue,
  toDateTimeInputValue,
} from "./utils";

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

  it("documents why the backend must always send an explicit UTC marker (Sprint 77)", () => {
    // RC-1 found this live in production: the backend used to serialize
    // naive-UTC datetimes with a bare Python .isoformat() (no "Z"/offset),
    // and `new Date(...)` here reads a timezone-less ISO string as *local*
    // browser time, not UTC. Fixed at the source (app/core/time.py::
    // to_iso_utc, used by every API response) rather than by making this
    // function lenient — every timestamp the API sends now always carries
    // an explicit marker, so this demonstrates the failure mode the fix
    // closes, not a case this function itself needs to handle.
    const nowUtc = new Date();
    const timezoneLessString = nowUtc.toISOString().replace("Z", "");
    const properlyMarkedString = nowUtc.toISOString();

    const browserOffsetMinutes = nowUtc.getTimezoneOffset();
    if (browserOffsetMinutes === 0) {
      // The CI/dev machine happens to run in UTC — the two strings parse
      // identically here, so there's nothing to contrast; skip rather than
      // assert a tautology.
      return;
    }

    expect(formatRelativeTime(timezoneLessString)).not.toBe(
      formatRelativeTime(properlyMarkedString),
    );
    expect(formatRelativeTime(properlyMarkedString)).toBe("just now");
  });
});

describe("describeWhatsAppConnection", () => {
  it("maps each real backend status to honest, non-stale copy", () => {
    expect(describeWhatsAppConnection("connected")).toEqual({
      label: "Connected",
      variant: "success",
    });
    expect(describeWhatsAppConnection("pending_verification")).toEqual({
      label: "Needs attention",
      variant: "warning",
    });
    expect(describeWhatsAppConnection("not_connected")).toEqual({
      label: "Not connected",
      variant: "secondary",
    });
  });

  it("defaults to 'Not connected' rather than a stale/invented claim", () => {
    expect(describeWhatsAppConnection(undefined)).toEqual({
      label: "Not connected",
      variant: "secondary",
    });
  });
});

describe("toDateInputValue", () => {
  it("extracts the YYYY-MM-DD portion of an ISO datetime", () => {
    expect(toDateInputValue("2026-08-01T10:00:00")).toBe("2026-08-01");
  });

  it("returns an empty string for null", () => {
    expect(toDateInputValue(null)).toBe("");
  });

  it("returns an empty string for an invalid date", () => {
    expect(toDateInputValue("not-a-date")).toBe("");
  });
});

describe("toDateTimeInputValue", () => {
  it("extracts the YYYY-MM-DDTHH:mm portion of an ISO datetime", () => {
    expect(toDateTimeInputValue("2026-08-01T10:30:00")).toBe("2026-08-01T10:30");
  });

  it("returns an empty string for an invalid date", () => {
    expect(toDateTimeInputValue("not-a-date")).toBe("");
  });
});
