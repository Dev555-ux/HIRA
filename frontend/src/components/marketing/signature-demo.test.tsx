import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SignatureDemo } from "./signature-demo";

function setDocumentHidden(hidden: boolean) {
  Object.defineProperty(document, "hidden", { value: hidden, configurable: true });
  act(() => {
    document.dispatchEvent(new Event("visibilitychange"));
  });
}

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

// Mirrors BEATS' hold values in signature-demo.tsx exactly, in order.
const HOLDS_MS = [
  1400, 700, 2200, 1200, 650, 2000, 1200, 750, 1300, 2200, 1200, 650, 2200, 3400,
];

// Each beat's setTimeout is only (re-)registered once React has flushed the
// effect from the *previous* one, so a single advanceTimersByTime call —
// however large — only ever fires the one timer already pending; the chain
// needs one act()-wrapped advance per hop, not one big jump.
function advance(ms: number) {
  act(() => vi.advanceTimersByTime(ms));
}

describe("SignatureDemo", () => {
  beforeEach(() => {
    mockReducedMotion(false);
  });

  it("shows the opening message immediately and marks the first step active — no timer needed", () => {
    render(<SignatureDemo />);

    expect(screen.getByText(/looking for a luxury suv/i)).toBeInTheDocument();
    expect(screen.getByText("Searching Business Knowledge")).toBeInTheDocument();
  });

  it("tells the whole story from a single static frame: conversation and the six-step trace both present", () => {
    render(<SignatureDemo />);

    // The point of the two-panel design: every step label is visible
    // (in whatever status) from the very first paint, not just the one
    // currently active — the visitor should never need to wait to see
    // the shape of the whole story.
    for (const label of [
      "Searching Business Knowledge",
      "Found matching inventory",
      "Explaining financing",
      "Checking calendar availability",
      "Booking appointment",
      "Escalating to sales specialist",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("exposes one accessible label instead of letting screen readers read every animated bubble", () => {
    render(<SignatureDemo />);

    const group = screen.getByRole("group");
    expect(group).toHaveAccessibleName(/customer asks about suvs on whatsapp/i);
    // The animated content itself must never be independently reachable —
    // an aria-hidden focusable descendant is an accessibility violation.
    expect(group.querySelector('[aria-hidden="true"] [tabindex]')).toBeNull();
  });

  it("advances the conversation and the intelligence trace in lockstep", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    advance(HOLDS_MS[0]); // -> typing
    expect(document.querySelector(".animate-typing-dot")).not.toBeNull();

    advance(HOLDS_MS[1]); // -> HIRA's SUV reply; search+found complete together
    expect(screen.getByText(/we've got the bmw x7/i)).toBeInTheDocument();

    advance(HOLDS_MS[2]); // -> "Can I finance the X7?"
    expect(screen.getByText(/can i finance the x7/i)).toBeInTheDocument();

    advance(HOLDS_MS[3]); // -> typing, financing step active
    advance(HOLDS_MS[4]); // -> HIRA's financing answer
    expect(screen.getByText(/up to 84 months/i)).toBeInTheDocument();

    advance(HOLDS_MS[5]); // -> "Book me a test drive tomorrow"
    advance(HOLDS_MS[6]); // -> typing, calendar step active
    advance(HOLDS_MS[7]); // -> still typing, calendar done + booking active
    advance(HOLDS_MS[8]); // -> booking confirmation
    expect(screen.getByText(/booked!/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("shows the payoff line only once every step has resolved, then loops back", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    expect(screen.getByText(/didn't have to lift a finger/i)).toHaveClass("opacity-0");

    // Advancing through every beat up to (and including) the payoff beat
    // itself — HOLDS_MS[i] is CURRENT beat i's hold, so advancing through
    // indices 0..12 lands on beat 13 (payoff), which is already applied.
    for (const ms of HOLDS_MS.slice(0, -1)) {
      advance(ms);
    }
    expect(screen.getByText(/escalating to sales specialist/i)).toBeInTheDocument();
    expect(screen.getByText(/of course — priya/i)).toBeInTheDocument();
    expect(screen.getByText(/didn't have to lift a finger/i)).toHaveClass("opacity-100");

    // Waiting out the payoff beat's own hold triggers the loop-back reset.
    advance(HOLDS_MS[HOLDS_MS.length - 1]);
    expect(screen.getByText(/looking for a luxury suv/i)).toBeInTheDocument();
    expect(screen.queryByText(/of course — priya/i)).toBeNull();

    vi.useRealTimers();
  });

  it("pauses on hover and resumes when the mouse leaves", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);
    const group = screen.getByRole("group");

    fireEvent.mouseEnter(group);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    expect(screen.queryByText(/we've got the bmw x7/i)).toBeNull();

    fireEvent.mouseLeave(group);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    expect(screen.getByText(/we've got the bmw x7/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("pauses on keyboard focus and resumes on blur", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);
    const group = screen.getByRole("group");

    fireEvent.focus(group);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    expect(screen.queryByText(/we've got the bmw x7/i)).toBeNull();

    fireEvent.blur(group);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    expect(screen.getByText(/we've got the bmw x7/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("pauses while the browser tab is hidden and resumes when it's visible again", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    setDocumentHidden(true);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    expect(screen.queryByText(/we've got the bmw x7/i)).toBeNull();

    setDocumentHidden(false);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    expect(screen.getByText(/we've got the bmw x7/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("renders a fully resolved, static version of both panels for prefers-reduced-motion — no timers, no looping", () => {
    mockReducedMotion(true);
    render(<SignatureDemo />);

    expect(screen.getByRole("img", { name: /customer asks about suvs on whatsapp/i })).toBeInTheDocument();
    expect(screen.getByText(/looking for a luxury suv/i)).toBeInTheDocument();
    expect(screen.getByText(/of course — priya/i)).toBeInTheDocument();
    expect(screen.getByText(/didn't have to lift a finger/i)).toHaveClass("opacity-100");
  });

  afterEach(() => {
    vi.useRealTimers();
  });
});
