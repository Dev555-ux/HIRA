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

function indicatorFor(label: string) {
  const labelEl = screen.getByText(label);
  return labelEl.parentElement?.querySelector("span");
}

// Mirrors BEATS' hold values in signature-demo.tsx exactly, in order.
const HOLDS_MS = [1500, 500, 300, 600, 200, 500, 100, 300, 100, 300, 200, 100, 800, 400, 700, 2200, 3200, 600];

function advance(ms: number) {
  act(() => vi.advanceTimersByTime(ms));
}

describe("SignatureDemo", () => {
  beforeEach(() => {
    mockReducedMotion(false);
  });

  it("opens idle: no message, no reply, no closing line, nothing moving", () => {
    render(<SignatureDemo />);

    expect(screen.queryByText(/do you have anything in a bmw x7/i)).toBeNull();
    expect(screen.queryByText(/booked for tomorrow/i)).toBeNull();
    expect(screen.queryByText(/this is hira/i)).toBeNull();
    expect(indicatorFor("Knowledge")).toHaveClass("border-border/50");
  });

  it("exposes one accessible label instead of narrating six systems to screen readers", () => {
    render(<SignatureDemo />);

    const group = screen.getByRole("group");
    expect(group).toHaveAccessibleName(/six business systems/i);
    // The animated content itself must never be independently reachable —
    // an aria-hidden focusable descendant is an accessibility violation.
    expect(group.querySelector('[aria-hidden="true"] [tabindex]')).toBeNull();
  });

  it("lets systems overlap — CRM starts while Knowledge is still active, not a rigid queue", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    advance(HOLDS_MS[0]); // message appears
    advance(HOLDS_MS[1]); // brief pause
    advance(HOLDS_MS[2]); // Knowledge -> active
    expect(indicatorFor("Knowledge")).toHaveClass("border-primary");
    // Evidence of work, not just a colored dot: the working verb shows while active.
    expect(screen.getByText("Searching…")).toHaveClass("opacity-100");

    advance(HOLDS_MS[3]); // CRM -> active, while Knowledge is still active (not done until beat 7)
    expect(indicatorFor("Knowledge")).toHaveClass("border-primary");
    expect(indicatorFor("CRM")).toHaveClass("border-primary");

    vi.useRealTimers();
  });

  it("shows a travelling pulse on an active cable and removes it once that system finishes", () => {
    vi.useFakeTimers();
    const { container } = render(<SignatureDemo />);

    // Knowledge's line ends at x2=70 (its wide-layout position) — look it up
    // directly rather than "any pulsing line", since other systems overlap
    // and stay active after Knowledge finishes. The pulse is a separate
    // overlay line sharing the same endpoint, so filter on its class too.
    const knowledgePulse = () =>
      Array.from(container.querySelectorAll("svg line.animate-signature-pulse")).find(
        (line) => line.getAttribute("x2") === "70",
      );

    for (const ms of HOLDS_MS.slice(0, 3)) advance(ms); // Knowledge -> active
    expect(knowledgePulse()).toHaveAttribute("stroke-dasharray", "6 94");

    for (const ms of HOLDS_MS.slice(3, 7)) advance(ms); // Knowledge -> done
    expect(knowledgePulse()).toBeUndefined();

    vi.useRealTimers();
  });

  it("advances every system through active -> done at its own pace", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    for (const ms of HOLDS_MS.slice(0, 7)) advance(ms); // through "Knowledge -> done"
    expect(screen.getByText("→ Verified")).toHaveClass("opacity-100");

    for (const ms of HOLDS_MS.slice(7, 10)) advance(ms); // through "CRM -> done"
    expect(screen.getByText("→ Customer found")).toHaveClass("opacity-100");

    for (const ms of HOLDS_MS.slice(10, 13)) advance(ms); // through "Finance -> done"
    expect(screen.getByText("→ Quote ready")).toHaveClass("opacity-100");

    vi.useRealTimers();
  });

  it("settles every system in the same instant once all six have finished", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    for (const ms of HOLDS_MS.slice(0, 13)) advance(ms); // through the "calendar done + team done" beat

    // Not yet settled: done systems still show their own success color.
    expect(screen.getByText("→ Tuesday · 2 PM")).toHaveClass("opacity-100");

    advance(HOLDS_MS[13]); // the settle beat itself
    // Every system's indicator shares the exact same resting classes now.
    for (const label of ["Knowledge", "CRM", "Inventory", "Finance", "Calendar", "Human Team"]) {
      expect(indicatorFor(label)).toHaveClass("border-foreground/40");
    }
    // The calm moment silences the evidence too — status text fades away
    // with the accent colors, not just the indicator dots.
    expect(screen.getByText("→ Tuesday · 2 PM")).toHaveClass("opacity-0");

    vi.useRealTimers();
  });

  it("shows the reply last and smallest, then the closing line, then resets", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    for (const ms of HOLDS_MS.slice(0, 14)) advance(ms); // through the settle beat (index 14)
    expect(screen.queryByText(/booked for tomorrow/i)).toBeNull();

    advance(HOLDS_MS[14]); // -> reply beat (index 15)
    expect(screen.getByText(/booked for tomorrow/i)).toBeInTheDocument();

    advance(HOLDS_MS[15]); // -> closing beat (index 16)
    expect(screen.getByText(/this is hira/i)).toBeInTheDocument();
    expect(screen.getByText(/one message\. six business systems\. zero manual work\./i)).toBeInTheDocument();

    advance(HOLDS_MS[16]); // -> index 17, closing still holding
    advance(HOLDS_MS[17]); // -> wraps past the end, resets
    expect(screen.queryByText(/this is hira/i)).toBeNull();
    expect(screen.queryByText(/do you have anything in a bmw x7/i)).toBeNull();
    expect(indicatorFor("Knowledge")).toHaveClass("border-border/50");

    vi.useRealTimers();
  });

  it("pauses on hover and resumes when the mouse leaves", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);
    const group = screen.getByRole("group");

    fireEvent.mouseEnter(group);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    expect(screen.queryByText(/do you have anything in a bmw x7/i)).toBeNull();

    fireEvent.mouseLeave(group);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    expect(screen.getByText(/do you have anything in a bmw x7/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("pauses on keyboard focus and resumes on blur", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);
    const group = screen.getByRole("group");

    fireEvent.focus(group);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    expect(screen.queryByText(/do you have anything in a bmw x7/i)).toBeNull();

    fireEvent.blur(group);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    expect(screen.getByText(/do you have anything in a bmw x7/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("pauses while the browser tab is hidden and resumes when it's visible again", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    setDocumentHidden(true);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    expect(screen.queryByText(/do you have anything in a bmw x7/i)).toBeNull();

    setDocumentHidden(false);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    expect(screen.getByText(/do you have anything in a bmw x7/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("renders a fully resolved, static composition for prefers-reduced-motion — no timers, no looping", () => {
    mockReducedMotion(true);
    render(<SignatureDemo />);

    expect(screen.getByRole("img", { name: /six business systems/i })).toBeInTheDocument();
    expect(screen.getByText(/do you have anything in a bmw x7/i)).toBeInTheDocument();
    expect(screen.getByText(/booked for tomorrow/i)).toBeInTheDocument();
    expect(screen.getByText("→ Sales notified")).toHaveClass("opacity-100");
  });

  afterEach(() => {
    vi.useRealTimers();
  });
});
