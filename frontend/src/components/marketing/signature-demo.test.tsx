import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SignatureDemo } from "./signature-demo";

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

describe("SignatureDemo", () => {
  beforeEach(() => {
    mockReducedMotion(false);
  });

  it("shows the opening line immediately, with no timer needed", () => {
    render(<SignatureDemo />);

    expect(screen.getByText(/looking for a luxury suv/i)).toBeInTheDocument();
  });

  it("exposes one accessible label instead of letting screen readers read every animated bubble", () => {
    render(<SignatureDemo />);

    const group = screen.getByRole("group");
    expect(group).toHaveAccessibleName(/customer asks about suvs/i);
    // The animated content itself must never be independently reachable —
    // an aria-hidden focusable descendant is an accessibility violation.
    expect(group.querySelector('[aria-hidden="true"] [tabindex]')).toBeNull();
  });

  // Each beat's setTimeout is only (re-)registered once React has flushed
  // the effect from the *previous* one, so a single advanceTimersByTime
  // call — however large — only ever fires the one timer already pending;
  // the chain needs one act()-wrapped advance per hop, not one big jump.
  const HOLDS_MS = [900, 900, 2800, 1600, 800, 2600, 1600, 800, 1200, 2800, 1600, 800, 2800, 3500];

  function advance(ms: number) {
    act(() => vi.advanceTimersByTime(ms));
  }

  it("advances through the script over time: typing, then HIRA's reply, then the booking", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    advance(HOLDS_MS[0]); // -> typing
    expect(document.querySelector(".animate-typing-dot")).not.toBeNull();

    advance(HOLDS_MS[1]); // -> HIRA's SUV list
    expect(screen.getByText(/would you like to compare them/i)).toBeInTheDocument();

    advance(HOLDS_MS[2]); // -> "Can I finance the BMW X7?"
    expect(screen.getByText(/can i finance the bmw x7/i)).toBeInTheDocument();

    advance(HOLDS_MS[3]); // -> typing
    advance(HOLDS_MS[4]); // -> HIRA's financing answer
    expect(screen.getByText(/up to 84 months/i)).toBeInTheDocument();

    advance(HOLDS_MS[5]); // -> "Book me for a test drive tomorrow."
    advance(HOLDS_MS[6]); // -> typing
    advance(HOLDS_MS[7]); // -> "Checking calendar…"
    expect(screen.getByText(/checking calendar/i)).toBeInTheDocument();

    advance(HOLDS_MS[8]); // -> booking confirmation
    expect(screen.getByText(/booked!/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("loops back to the opening line after the closing card", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    for (const ms of HOLDS_MS) {
      advance(ms);
    }

    expect(screen.getByText(/looking for a luxury suv/i)).toBeInTheDocument();
    expect(screen.queryByText(/booked!/i)).toBeNull();

    vi.useRealTimers();
  });

  it("renders a fully static, complete conversation for prefers-reduced-motion — no timers, no looping", () => {
    mockReducedMotion(true);
    render(<SignatureDemo />);

    expect(screen.getByRole("img", { name: /customer asks about suvs/i })).toBeInTheDocument();
    expect(screen.getByText(/looking for a luxury suv/i)).toBeInTheDocument();
    expect(screen.getByText(/booked!/i)).toBeInTheDocument();
    expect(screen.getByText(/sales specialist/i)).toBeInTheDocument();
  });

  afterEach(() => {
    vi.useRealTimers();
  });
});
