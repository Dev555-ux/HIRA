import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ScenarioId } from "./signature-demo";
import { DEFAULT_SCENARIO_ID, SCENARIOS, SignatureDemo } from "./signature-demo";

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
const HOLDS_MS = [1400, 500, 300, 700, 300, 500, 200, 400, 300, 700, 400, 700, 2200, 3200, 600];

function advance(ms: number) {
  act(() => vi.advanceTimersByTime(ms));
}

describe("SignatureDemo", () => {
  beforeEach(() => {
    mockReducedMotion(false);
  });

  it("opens idle: no message, no reply, no closing line, nothing moving", () => {
    render(<SignatureDemo />);

    expect(screen.queryByText(/do you have availability for a cleaning/i)).toBeNull();
    expect(screen.queryByText(/thursday at 10:00 am works/i)).toBeNull();
    expect(screen.queryByText(/this is hira/i)).toBeNull();
    expect(indicatorFor("Knowledge")).toHaveClass("border-border/50");
  });

  it("exposes one accessible label instead of narrating four systems to screen readers", () => {
    render(<SignatureDemo />);

    const group = screen.getByRole("group");
    expect(group).toHaveAccessibleName(/four.*systems/i);
    // The animated content itself must never be independently reachable —
    // an aria-hidden focusable descendant is an accessibility violation.
    expect(group.querySelector('[aria-hidden="true"] [tabindex]')).toBeNull();
  });

  it("lets systems overlap — CRM starts while Knowledge is still active, not a rigid queue", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    for (const ms of HOLDS_MS.slice(0, 3)) advance(ms); // -> Knowledge active
    expect(indicatorFor("Knowledge")).toHaveClass("border-primary");
    expect(screen.getByText("Searching…")).toHaveClass("opacity-100");

    advance(HOLDS_MS[3]); // -> CRM active, while Knowledge is still active
    expect(indicatorFor("Knowledge")).toHaveClass("border-primary");
    expect(indicatorFor("CRM")).toHaveClass("border-primary");

    vi.useRealTimers();
  });

  it("shows a travelling pulse on an active cable, radiating from the hub, and removes it once that system finishes", () => {
    vi.useFakeTimers();
    const { container } = render(<SignatureDemo />);

    const knowledgePulse = () =>
      container.querySelector("svg line.animate-signature-pulse[x2='50'][y2='12']");

    for (const ms of HOLDS_MS.slice(0, 3)) advance(ms); // -> Knowledge active
    expect(knowledgePulse()).toHaveAttribute("stroke-dasharray", "8 92");

    advance(HOLDS_MS[3]); // -> CRM active
    advance(HOLDS_MS[4]); // -> Knowledge done
    expect(knowledgePulse()).toBeNull();

    vi.useRealTimers();
  });

  it("advances every system through active -> done at its own pace", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    for (const ms of HOLDS_MS.slice(0, 5)) advance(ms); // -> Knowledge done
    expect(screen.getByText("→ Verified")).toHaveClass("opacity-100");

    for (const ms of HOLDS_MS.slice(5, 7)) advance(ms); // -> CRM done
    expect(screen.getByText("→ Customer found")).toHaveClass("opacity-100");

    for (const ms of HOLDS_MS.slice(7, 10)) advance(ms); // -> Team done
    expect(screen.getByText("→ Team notified")).toHaveClass("opacity-100");

    vi.useRealTimers();
  });

  it("settles every system and the hub in the same instant once all four have finished", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    for (const ms of HOLDS_MS.slice(0, 10)) advance(ms); // -> Team done (last one)

    expect(screen.getByText("→ Thu · 10:00 AM")).toHaveClass("opacity-100");

    advance(HOLDS_MS[10]); // the settle beat itself
    for (const label of ["Knowledge", "CRM", "Calendar", "Team"]) {
      expect(indicatorFor(label)).toHaveClass("border-foreground/40");
    }
    expect(screen.getByText("→ Thu · 10:00 AM")).toHaveClass("opacity-0");

    vi.useRealTimers();
  });

  it("shows the reply last, then the closing line, then resets", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    for (const ms of HOLDS_MS.slice(0, 11)) advance(ms); // through the settle beat
    expect(screen.queryByText(/thursday at 10:00 am works/i)).toBeNull();

    advance(HOLDS_MS[11]); // -> reply beat
    expect(screen.getByText(/thursday at 10:00 am works/i)).toBeInTheDocument();

    advance(HOLDS_MS[12]); // -> closing beat
    expect(screen.getByText(/this is hira/i)).toBeInTheDocument();
    expect(
      screen.getByText(/one message\. four business systems\. zero manual work\./i),
    ).toBeInTheDocument();

    advance(HOLDS_MS[13]); // closing still holding
    advance(HOLDS_MS[14]); // wraps past the end, resets
    expect(screen.queryByText(/this is hira/i)).toBeNull();
    expect(screen.queryByText(/do you have availability for a cleaning/i)).toBeNull();
    expect(indicatorFor("Knowledge")).toHaveClass("border-border/50");

    vi.useRealTimers();
  });

  it("replays the full sequence identically on a second loop (Sprint 66 PR-2)", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    const runOneLoop = () => {
      for (const ms of HOLDS_MS.slice(0, 11)) advance(ms); // through the settle beat
      advance(HOLDS_MS[11]); // -> reply beat
      expect(screen.getByText(/thursday at 10:00 am works/i)).toBeInTheDocument();

      advance(HOLDS_MS[12]); // -> closing beat
      expect(screen.getByText(/this is hira/i)).toBeInTheDocument();
      // The reply bubble is replaced by the closing overlay, not stacked on it.
      expect(screen.queryByText(/thursday at 10:00 am works/i)).toBeNull();

      advance(HOLDS_MS[13]); // closing still holding
      advance(HOLDS_MS[14]); // wraps past the end, resets to idle
      expect(screen.queryByText(/this is hira/i)).toBeNull();
      expect(screen.queryByText(/do you have availability for a cleaning/i)).toBeNull();
    };

    // Replay: the identical sequence reproduces on the second pass, not a
    // one-shot animation that goes stale after the first run.
    runOneLoop();
    runOneLoop();

    vi.useRealTimers();
  });

  it("pauses on hover and resumes when the mouse leaves", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);
    const group = screen.getByRole("group");

    fireEvent.mouseEnter(group);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    expect(screen.queryByText(/do you have availability for a cleaning/i)).toBeNull();

    fireEvent.mouseLeave(group);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    expect(screen.getByText(/do you have availability for a cleaning/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("pauses on keyboard focus and resumes on blur", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);
    const group = screen.getByRole("group");

    fireEvent.focus(group);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    expect(screen.queryByText(/do you have availability for a cleaning/i)).toBeNull();

    fireEvent.blur(group);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    expect(screen.getByText(/do you have availability for a cleaning/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("pauses while the browser tab is hidden and resumes when it's visible again", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    setDocumentHidden(true);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    expect(screen.queryByText(/do you have availability for a cleaning/i)).toBeNull();

    setDocumentHidden(false);
    advance(HOLDS_MS[0]);
    advance(HOLDS_MS[1]);
    expect(screen.getByText(/do you have availability for a cleaning/i)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("renders a fully resolved, static composition for prefers-reduced-motion — no timers, no looping", () => {
    mockReducedMotion(true);
    render(<SignatureDemo />);

    expect(screen.getByRole("img", { name: /four.*systems/i })).toBeInTheDocument();
    expect(screen.getByText(/do you have availability for a cleaning/i)).toBeInTheDocument();
    expect(screen.getByText(/thursday at 10:00 am works/i)).toBeInTheDocument();
    expect(screen.getByText("→ Team notified")).toHaveClass("opacity-100");
  });

  afterEach(() => {
    vi.useRealTimers();
  });
});

// Sprint 66 PR-2 — BEATS (a single hardcoded sequence) became SCENARIOS (a
// named sequence per scenario). No selector UI exists yet to switch between
// them, so these are data-contract tests, not rendered-component tests:
// they prove the data itself is sound and that any future scenario swap
// hits the engine's one existing reset path cleanly, without needing
// per-scenario reset logic.
describe("SCENARIOS data model (Sprint 66 PR-2)", () => {
  it("defaults to the cleaning scenario — today's only rendered one", () => {
    expect(DEFAULT_SCENARIO_ID).toBe("cleaning");
  });

  it("keeps the cleaning scenario's copy and timing exactly as before the refactor", () => {
    const { cleaning } = SCENARIOS;
    expect(cleaning.customerMessage).toBe("Do you have availability for a cleaning this Thursday?");
    expect(cleaning.replyMessage).toBe("Thursday at 10:00 AM works — you're all set!");
    expect(cleaning.beats.map((beat) => beat.hold)).toEqual(HOLDS_MS);
  });

  it("defines all four scenarios named in the ticket, each self-consistent", () => {
    const ids: ScenarioId[] = ["cleaning", "dental", "pricing", "escalation"];
    expect(Object.keys(SCENARIOS).sort()).toEqual([...ids].sort());

    for (const id of ids) {
      const scenario = SCENARIOS[id];
      expect(scenario.id).toBe(id);
      expect(scenario.chipLabel.length).toBeGreaterThan(0);
      expect(scenario.customerMessage.length).toBeGreaterThan(0);
      expect(scenario.replyMessage.length).toBeGreaterThan(0);

      // Ends in exactly one closing beat, followed by one reset hold —
      // the shape the engine's loop-wrap branch depends on.
      const closingCount = scenario.beats.filter((beat) => beat.closing).length;
      expect(closingCount).toBe(1);
      expect(scenario.beats.at(-1)?.closing).toBeUndefined();
    }
  });

  it("switching to any scenario resets correctly: every one opens on a bare idle hold", () => {
    // The engine's reset branch always returns to IDLE_STATUS with nothing
    // else visible. A scenario swap only resets cleanly if the scenario it
    // swaps to also opens that way — proven here for all four, so no
    // scenario can ever open "mid-sequence."
    for (const scenario of Object.values(SCENARIOS)) {
      expect(scenario.beats[0]).toEqual({ hold: scenario.beats[0].hold });
    }
  });
});
