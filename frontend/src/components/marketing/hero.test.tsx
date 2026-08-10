import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Hero } from "./hero";

function mockReducedMotion(matches: boolean) {
  window.matchMedia = ((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as typeof window.matchMedia;
}

// Mirrors HOLDS_MS in hero.tsx exactly, in order.
const HOLDS_MS = [120, 1200, 1800, 700, 700, 1400];

function advance(ms: number) {
  act(() => vi.advanceTimersByTime(ms));
}

function markElement() {
  return screen.getByText("customer message").closest("mark");
}

describe("Hero", () => {
  beforeEach(() => {
    mockReducedMotion(false);
  });

  it("keeps the headline in the DOM and neutral before the demo resolves", () => {
    render(<Hero />);

    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(markElement()).toHaveClass("bg-muted");
    expect(markElement()).not.toHaveClass("bg-brand/15");
  });

  it("plays the demo once, event-driven through each stage, then freezes", () => {
    vi.useFakeTimers();
    render(<Hero />);

    advance(HOLDS_MS[0]); // -> message
    expect(screen.getByText(/do you have availability for a cleaning/i)).toBeInTheDocument();

    advance(HOLDS_MS[1]); // -> processing
    expect(screen.getByLabelText("HIRA is working")).toBeInTheDocument();

    advance(HOLDS_MS[2]); // -> knowledge (working)
    expect(screen.getByText("Using Business Knowledge")).toBeInTheDocument();

    advance(HOLDS_MS[3]); // -> calendar (knowledge done, calendar working)
    expect(screen.getByText("Calendar checked")).toBeInTheDocument();

    advance(HOLDS_MS[4]); // -> draft
    expect(screen.getByText(/thursday at 10:00 am works/i)).toBeInTheDocument();

    advance(HOLDS_MS[5]); // -> resolved
    expect(screen.getByText("No action required")).toBeInTheDocument();
    expect(screen.getByText("Customer confirmed")).toBeInTheDocument();
    expect(screen.getByText("Appointment booked")).toBeInTheDocument();
    expect(screen.getByText("Calendar updated")).toBeInTheDocument();

    // Synchronized: the headline mark resolves into the brand accent at the
    // same moment the outcome lands.
    expect(markElement()).toHaveClass("bg-brand/15");

    // Frozen, not looping: advancing well past the sequence changes nothing.
    advance(10_000);
    expect(screen.getByText("No action required")).toBeInTheDocument();
    expect(screen.queryByText(/thursday at 10:00 am works/i)).toBeNull();

    vi.useRealTimers();
  });

  it("renders a fully resolved, static composition for prefers-reduced-motion — no timers", () => {
    mockReducedMotion(true);
    render(<Hero />);

    expect(screen.getByRole("img", { name: /live product demonstration/i })).toBeInTheDocument();
    expect(screen.getByText("No action required")).toBeInTheDocument();
    expect(markElement()).toHaveClass("bg-brand/15");
  });

  afterEach(() => {
    vi.useRealTimers();
  });
});
