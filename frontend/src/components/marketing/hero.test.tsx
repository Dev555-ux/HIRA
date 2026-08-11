import { act, fireEvent, render, screen } from "@testing-library/react";
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

// Mirrors HOLDS_MS / RESOLVED_HOLD_MS in hero.tsx exactly.
const HOLDS_MS = [400, 1800, 2600, 1600, 1600, 2400];
const RESOLVED_HOLD_MS = 6500;

function advance(ms: number) {
  act(() => vi.advanceTimersByTime(ms));
}

function markElement() {
  return screen.getByText("customer message").closest("mark");
}

function playPauseButton() {
  return screen.getByRole("button", { name: /replay demo|pause demo|resume demo/i });
}

// jsdom has no IntersectionObserver, so useInView's documented fallback
// (setInView(true) when the API is missing) makes the demo "in view" as
// soon as it mounts — this is what drives autoplay-on-first-load in tests.
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

  it("autoplays on mount (first load) with no user action required", () => {
    vi.useFakeTimers();
    render(<Hero />);

    expect(playPauseButton()).toHaveAccessibleName("Pause demo");

    advance(HOLDS_MS[0]);
    expect(screen.getByText(/do you have availability for a cleaning/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("plays every stage in order at the slower V5.1 pace, then resolves", () => {
    vi.useFakeTimers();
    render(<Hero />);

    advance(HOLDS_MS[0]); // -> message
    expect(screen.getByText(/do you have availability for a cleaning/i)).toBeInTheDocument();

    advance(HOLDS_MS[1]); // -> processing
    expect(screen.getByLabelText("HIRA is working")).toBeInTheDocument();

    advance(HOLDS_MS[2]); // -> knowledge
    expect(screen.getByText("Using Business Knowledge")).toBeInTheDocument();

    advance(HOLDS_MS[3]); // -> calendar
    expect(screen.getByText("Calendar checked")).toBeInTheDocument();

    advance(HOLDS_MS[4]); // -> draft
    expect(screen.getByText(/thursday at 10:00 am works/i)).toBeInTheDocument();

    advance(HOLDS_MS[5]); // -> resolved
    expect(screen.getByText("No action required")).toBeInTheDocument();
    expect(markElement()).toHaveClass("bg-brand/15");

    vi.useRealTimers();
  });

  it("keeps the resolved outcome visible for the full hold, then settles back to idle ready to replay", () => {
    vi.useFakeTimers();
    render(<Hero />);
    for (const ms of HOLDS_MS) advance(ms);
    expect(screen.getByText("No action required")).toBeInTheDocument();

    advance(RESOLVED_HOLD_MS - 500);
    expect(screen.getByText("No action required")).toBeInTheDocument();

    advance(500);
    expect(screen.queryByText("No action required")).toBeNull();
    expect(markElement()).toHaveClass("bg-muted");
    expect(playPauseButton()).toHaveAccessibleName("Replay demo");

    vi.useRealTimers();
  });

  it("does not auto-loop while continuously in view — stays idle after settling until replayed", () => {
    vi.useFakeTimers();
    render(<Hero />);
    for (const ms of HOLDS_MS) advance(ms);
    advance(RESOLVED_HOLD_MS);
    expect(screen.queryByText("No action required")).toBeNull();

    advance(20_000);
    expect(screen.queryByText("No action required")).toBeNull();
    expect(screen.queryByText(/do you have availability/i)).toBeNull();

    vi.useRealTimers();
  });

  it("Pause freezes the current stage instead of continuing to advance", () => {
    vi.useFakeTimers();
    render(<Hero />);
    advance(HOLDS_MS[0]); // -> message
    fireEvent.click(playPauseButton());
    expect(playPauseButton()).toHaveAccessibleName("Resume demo");

    advance(HOLDS_MS[1] + 5000);
    expect(screen.queryByLabelText("HIRA is working")).toBeNull();
    expect(screen.getByText(/do you have availability for a cleaning/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("Resume continues from the paused stage instead of restarting", () => {
    vi.useFakeTimers();
    render(<Hero />);
    advance(HOLDS_MS[0]); // -> message
    fireEvent.click(playPauseButton()); // pause mid-message

    fireEvent.click(playPauseButton()); // resume
    expect(playPauseButton()).toHaveAccessibleName("Pause demo");
    // Still showing the message (not reset to idle) — resume, not replay.
    expect(screen.getByText(/do you have availability for a cleaning/i)).toBeInTheDocument();

    advance(HOLDS_MS[1]);
    expect(screen.getByLabelText("HIRA is working")).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("Replay restarts the sequence from the beginning once it has finished", () => {
    vi.useFakeTimers();
    render(<Hero />);
    for (const ms of HOLDS_MS) advance(ms);
    advance(RESOLVED_HOLD_MS); // -> settles back to idle
    expect(playPauseButton()).toHaveAccessibleName("Replay demo");

    fireEvent.click(playPauseButton()); // replay
    expect(playPauseButton()).toHaveAccessibleName("Pause demo");
    expect(screen.queryByText(/do you have availability for a cleaning/i)).toBeNull();

    advance(HOLDS_MS[0]);
    expect(screen.getByText(/do you have availability for a cleaning/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("renders a fully resolved, static composition for prefers-reduced-motion — no controls, no timers", () => {
    mockReducedMotion(true);
    render(<Hero />);

    expect(screen.getByRole("img", { name: /live product demonstration/i })).toBeInTheDocument();
    expect(screen.getByText("No action required")).toBeInTheDocument();
    expect(markElement()).toHaveClass("bg-brand/15");
    expect(screen.queryByRole("button", { name: /replay demo|pause demo|resume demo/i })).toBeNull();
  });

  afterEach(() => {
    vi.useRealTimers();
  });
});
