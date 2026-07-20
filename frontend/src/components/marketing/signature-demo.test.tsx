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

// Mirrors BEATS' hold values in signature-demo.tsx exactly, in order:
// intro, c1, typing, h1, c2, typing, h2, c3, typing, system, booking, c4,
// typing, h3, resolve, end.
const HOLDS_MS = [
  1600, 900, 900, 2600, 1500, 800, 2400, 1500, 800, 1100, 2600, 1500, 800, 2600, 1400, 3500,
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

  it("opens on a silent, message-free stage — the reveal is the point, not an accident of state", () => {
    render(<SignatureDemo />);

    expect(screen.queryByText(/looking for a luxury suv/i)).toBeNull();
    expect(screen.getByRole("group")).toBeInTheDocument();
  });

  it("exposes one accessible label instead of letting screen readers read every animated bubble", () => {
    render(<SignatureDemo />);

    const group = screen.getByRole("group");
    expect(group).toHaveAccessibleName(/customer asks about suvs/i);
    // The animated content itself must never be independently reachable —
    // an aria-hidden focusable descendant is an accessibility violation.
    expect(group.querySelector('[aria-hidden="true"] [tabindex]')).toBeNull();
  });

  it("advances through the script over time: intro, first message, typing, HIRA's reply, the booking", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    advance(HOLDS_MS[0]); // intro -> first customer message
    expect(screen.getByText(/looking for a luxury suv/i)).toBeInTheDocument();

    advance(HOLDS_MS[1]); // -> typing
    expect(document.querySelector(".animate-typing-dot")).not.toBeNull();

    advance(HOLDS_MS[2]); // -> HIRA's SUV list
    expect(screen.getByText(/would you like to compare them/i)).toBeInTheDocument();

    advance(HOLDS_MS[3]); // -> "Can I finance the BMW X7?"
    expect(screen.getByText(/can i finance the bmw x7/i)).toBeInTheDocument();

    advance(HOLDS_MS[4]); // -> typing
    advance(HOLDS_MS[5]); // -> HIRA's financing answer
    expect(screen.getByText(/up to 84 months/i)).toBeInTheDocument();

    advance(HOLDS_MS[6]); // -> "Book me for a test drive tomorrow."
    advance(HOLDS_MS[7]); // -> typing
    advance(HOLDS_MS[8]); // -> "Checking calendar…"
    expect(screen.getByText(/checking calendar/i)).toBeInTheDocument();

    advance(HOLDS_MS[9]); // -> booking confirmation
    expect(screen.getByText(/booked!/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("resolves and loops back to a silent stage after the closing card", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    for (const ms of HOLDS_MS) {
      advance(ms);
    }

    expect(screen.queryByText(/looking for a luxury suv/i)).toBeNull();
    expect(screen.queryByText(/booked!/i)).toBeNull();
    expect(screen.getByRole("group")).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("pauses on hover and resumes when the mouse leaves", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);
    const group = screen.getByRole("group");

    fireEvent.mouseEnter(group);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    advance(HOLDS_MS[2]);
    expect(screen.queryByText(/would you like to compare them/i)).toBeNull();

    fireEvent.mouseLeave(group);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    advance(HOLDS_MS[2]);
    expect(screen.getByText(/would you like to compare them/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("pauses on keyboard focus and resumes on blur", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);
    const group = screen.getByRole("group");

    fireEvent.focus(group);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    advance(HOLDS_MS[2]);
    expect(screen.queryByText(/would you like to compare them/i)).toBeNull();

    fireEvent.blur(group);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    advance(HOLDS_MS[2]);
    expect(screen.getByText(/would you like to compare them/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("pauses while the browser tab is hidden and resumes when it's visible again", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    setDocumentHidden(true);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    advance(HOLDS_MS[2]);
    expect(screen.queryByText(/would you like to compare them/i)).toBeNull();

    setDocumentHidden(false);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    advance(HOLDS_MS[2]);
    expect(screen.getByText(/would you like to compare them/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("renders a fully static, complete conversation for prefers-reduced-motion — no timers, no looping, no intro/resolve theatrics", () => {
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
