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
const HOLDS_MS = [600, 1300, 1900, 1500, 1700, 1400, 2000];
const RESOLVED_HOLD_MS = 5500;

function advance(ms: number) {
  act(() => vi.advanceTimersByTime(ms));
}

function markElement() {
  // Signal & Depth PR-2 narrowed the marked headline text from "customer
  // message" to the single accent word "message" — same mark, same
  // resolved-state mechanism, just naming what it actually wraps now.
  return screen.getByText("message").closest("mark");
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
    expect(screen.getByText(/book an ac service tomorrow after 3 pm/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("plays every stage in order — narrating the reasoning — then resolves", () => {
    vi.useFakeTimers();
    render(<Hero />);

    advance(HOLDS_MS[0]); // -> message
    expect(screen.getByText(/book an ac service tomorrow after 3 pm/i)).toBeInTheDocument();

    advance(HOLDS_MS[1]); // -> thinking
    expect(screen.getByLabelText("Thinking…")).toBeInTheDocument();

    advance(HOLDS_MS[2]); // -> checking
    expect(screen.getByLabelText("Checking technician availability…")).toBeInTheDocument();

    advance(HOLDS_MS[3]); // -> verified
    expect(screen.getByText("Calendar checked")).toBeInTheDocument();
    expect(screen.getByText("Service area verified")).toBeInTheDocument();
    expect(screen.getByText("Technician assigned")).toBeInTheDocument();

    advance(HOLDS_MS[4]); // -> reply
    expect(screen.getByText(/booked your service for tomorrow at 4:00 pm/i)).toBeInTheDocument();
    expect(screen.getByText(/assigned ravi to your service/i)).toBeInTheDocument();

    advance(HOLDS_MS[5]); // -> reserved
    expect(screen.getByText("Appointment confirmed")).toBeInTheDocument();

    advance(HOLDS_MS[6]); // -> resolved
    expect(screen.getByText("Reminder scheduled")).toBeInTheDocument();
    expect(markElement()).toHaveClass("bg-brand/15");

    vi.useRealTimers();
  });

  it("keeps the resolved outcome visible for the full hold, then settles back to idle ready to replay", () => {
    vi.useFakeTimers();
    render(<Hero />);
    for (const ms of HOLDS_MS) advance(ms);
    expect(screen.getByText("Reminder scheduled")).toBeInTheDocument();

    advance(RESOLVED_HOLD_MS - 500);
    expect(screen.getByText("Reminder scheduled")).toBeInTheDocument();

    advance(500);
    expect(screen.queryByText("Reminder scheduled")).toBeNull();
    expect(markElement()).toHaveClass("bg-muted");
    expect(playPauseButton()).toHaveAccessibleName("Replay demo");

    vi.useRealTimers();
  });

  it("does not auto-loop while continuously in view — stays idle after settling until replayed", () => {
    vi.useFakeTimers();
    render(<Hero />);
    for (const ms of HOLDS_MS) advance(ms);
    advance(RESOLVED_HOLD_MS);
    expect(screen.queryByText("Reminder scheduled")).toBeNull();

    advance(20_000);
    expect(screen.queryByText("Reminder scheduled")).toBeNull();
    expect(screen.queryByText(/book an ac service/i)).toBeNull();

    vi.useRealTimers();
  });

  it("Pause freezes the current stage instead of continuing to advance", () => {
    vi.useFakeTimers();
    render(<Hero />);
    advance(HOLDS_MS[0]); // -> message
    fireEvent.click(playPauseButton());
    expect(playPauseButton()).toHaveAccessibleName("Resume demo");

    advance(HOLDS_MS[1] + 5000);
    expect(screen.queryByLabelText("Thinking…")).toBeNull();
    expect(screen.getByText(/book an ac service tomorrow after 3 pm/i)).toBeInTheDocument();

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
    expect(screen.getByText(/book an ac service tomorrow after 3 pm/i)).toBeInTheDocument();

    advance(HOLDS_MS[1]);
    expect(screen.getByLabelText("Thinking…")).toBeInTheDocument();

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
    expect(screen.queryByText(/book an ac service tomorrow after 3 pm/i)).toBeNull();

    advance(HOLDS_MS[0]);
    expect(screen.getByText(/book an ac service tomorrow after 3 pm/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("renders a fully resolved, static composition for prefers-reduced-motion — no controls, no timers", () => {
    mockReducedMotion(true);
    render(<Hero />);

    expect(screen.getByRole("img", { name: /live product demonstration/i })).toBeInTheDocument();
    expect(screen.getByText("Reminder scheduled")).toBeInTheDocument();
    expect(markElement()).toHaveClass("bg-brand/15");
    expect(screen.queryByRole("button", { name: /replay demo|pause demo|resume demo/i })).toBeNull();
  });

  afterEach(() => {
    vi.useRealTimers();
  });
});
