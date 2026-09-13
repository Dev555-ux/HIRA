import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ScenarioId } from "./signature-demo";
import {
  DEFAULT_SCENARIO_ID,
  OrchestrationStage,
  SCENARIOS,
  ScenarioSelector,
} from "./signature-demo";

// Cinematic rebuild — the <SignatureDemo> section (selector + phone +
// graph, with the selector owning scenario state and `key` remounting the
// widget on change) no longer exists: hero.tsx composes those two exported
// pieces directly, in exactly this shape. This harness is that composition,
// so every behavioural test below still drives the same unit it always did
// — including the scenario-switch remount, which is the `key` prop here.
function SignatureDemo() {
  const [scenarioId, setScenarioId] = useState<ScenarioId>(DEFAULT_SCENARIO_ID);
  return (
    <>
      <ScenarioSelector scenarioId={scenarioId} onChange={setScenarioId} />
      <OrchestrationStage key={scenarioId} scenarioId={scenarioId} />
    </>
  );
}

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

    const group = screen.getByRole("group", { name: /four.*systems/i });
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
    const group = screen.getByRole("group", { name: /four.*systems/i });

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
    const group = screen.getByRole("group", { name: /four.*systems/i });

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
// named sequence per scenario). These are data-contract tests, not
// rendered-component tests: they prove the data itself is sound,
// independent of the selector UI PR-3 (below) added on top of it.
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

// Sprint 66 PR-3 — a native <input type="radio"> chip per scenario, wired
// to a `key={scenarioId}` remount of DemoWidget (see signature-demo.tsx).
// Keyboard behavior (Tab lands on the checked radio, arrow keys move and
// select) is real browser/jsdom radio-group behavior, not custom code —
// verified empirically here, not assumed.
describe("ScenarioSelector (Sprint 66 PR-3)", () => {
  beforeEach(() => {
    mockReducedMotion(false);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("selects every scenario, swapping the demo to that scenario's message", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    const expectations: [ScenarioId, RegExp][] = [
      ["cleaning", /do you have availability for a cleaning/i],
      ["dental", /consultation with dr\. martinez/i],
      ["pricing", /what do your plans include/i],
      ["escalation", /speak with your team about an urgent issue/i],
    ];

    for (const [id, messagePattern] of expectations) {
      const chip = screen.getByRole("radio", { name: new RegExp(`^${SCENARIOS[id].chipLabel}$`, "i") });
      fireEvent.click(chip);
      expect(chip).toBeChecked();

      // Every scenario opens with the same idle-then-message rhythm.
      advance(1400);
      advance(500);
      expect(screen.getByText(messagePattern)).toBeInTheDocument();
    }
  });

  it("replays after a scenario switch — the newly selected scenario loops just like the default did", () => {
    vi.useFakeTimers();
    render(<SignatureDemo />);

    fireEvent.click(screen.getByRole("radio", { name: /^Escalation$/i }));

    const holds = SCENARIOS.escalation.beats.map((beat) => beat.hold);
    const runOneLoop = () => {
      for (const ms of holds.slice(0, 7)) advance(ms); // through the settle beat
      advance(holds[7]); // -> reply beat
      expect(screen.getByText(/i've flagged this to your team/i)).toBeInTheDocument();

      advance(holds[8]); // -> closing beat
      expect(screen.getByText(/this is hira/i)).toBeInTheDocument();

      advance(holds[9]); // closing still holding
      advance(holds[10]); // wraps past the end, resets to idle
      expect(screen.queryByText(/this is hira/i)).toBeNull();
      expect(screen.queryByText(/speak with your team/i)).toBeNull();
    };

    runOneLoop();
    runOneLoop(); // replay: reproduces identically without touching the selector again
  });

  it("is keyboard navigable: Tab lands on the checked chip, arrow keys move and select", async () => {
    const user = userEvent.setup();
    render(<SignatureDemo />);

    const cleaningChip = screen.getByRole("radio", { name: /^Cleaning$/i });
    const dentalChip = screen.getByRole("radio", { name: /^Dental$/i });
    const pricingChip = screen.getByRole("radio", { name: /^Pricing$/i });

    expect(cleaningChip).toBeChecked();

    await user.tab();
    expect(cleaningChip).toHaveFocus();

    await user.keyboard("{ArrowRight}");
    expect(dentalChip).toHaveFocus();
    expect(dentalChip).toBeChecked();
    expect(cleaningChip).not.toBeChecked();

    await user.keyboard("{ArrowRight}");
    expect(pricingChip).toHaveFocus();
    expect(pricingChip).toBeChecked();
  });

  it("gives each chip a visible focus ring wired to peer-focus-visible", () => {
    render(<SignatureDemo />);

    const chip = screen.getByRole("radio", { name: /^Cleaning$/i });
    const visibleBadge = chip.nextElementSibling;
    expect(visibleBadge?.className).toContain("peer-focus-visible:ring-2");
  });

  it("exposes correct ARIA structure: a named group of four radios, one checked", () => {
    render(<SignatureDemo />);

    const group = screen.getByRole("group", { name: /choose a demo scenario/i });
    expect(group.tagName).toBe("FIELDSET");

    const radios = screen.getAllByRole("radio");
    expect(radios).toHaveLength(4);
    expect(radios.every((r) => r.getAttribute("name") === "signature-demo-scenario")).toBe(true);

    const checked = radios.filter((r) => (r as HTMLInputElement).checked);
    expect(checked).toHaveLength(1);
    expect(checked[0]).toHaveAccessibleName(/^Cleaning$/i);
  });

  it("respects reduced motion for any selected scenario, not just the default", () => {
    mockReducedMotion(true);
    render(<SignatureDemo />);

    fireEvent.click(screen.getByRole("radio", { name: /^Dental$/i }));

    expect(screen.getByText(/consultation with dr\. martinez/i)).toBeInTheDocument();
    expect(screen.getByText(/dr\. martinez has an opening tomorrow/i)).toBeInTheDocument();
  });
});
