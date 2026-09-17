import { render, screen, within } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
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

// Cinematic rebuild — this file previously drove the Hero's own chat state
// machine (STAGES/HOLDS_MS: thinking → checking → verified → reply →
// reserved → resolved, plus Pause/Resume/Replay). That component
// (ProductDemo) was deleted, not moved: the hero's stage is now the
// orchestration engine, whose own sequencing, pausing and reduced-motion
// behaviour are covered in full by signature-demo.test.tsx. What belongs
// here is what the Hero itself is now responsible for — the composition.
describe("Hero", () => {
  beforeEach(() => {
    mockReducedMotion(false);
  });

  it("leads with one h1 carrying the full promise", () => {
    render(<Hero />);

    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toBeInTheDocument();
    expect(heading).toHaveTextContent(/never miss another customer message\./i);
  });

  it("accents exactly one word, in brand colour and with no highlight chip", () => {
    render(<Hero />);

    const accent = screen.getByText("customer");
    expect(accent).toHaveClass("text-brand");
    // The old <mark> carried a resolved-state background from a demo that
    // no longer lives in this column; nothing should reintroduce one.
    expect(accent.closest("mark")).toBeNull();
  });

  it("offers a single undivided call to action pointing at sign-up", () => {
    render(<Hero />);

    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute("href", "/sign-up");
    expect(links[0]).toHaveAccessibleName(/get started/i);
  });

  it("names the audience as a real semantic list inside the copy rail", () => {
    render(<Hero />);

    expect(screen.getByText(/trusted by modern businesses/i)).toBeInTheDocument();
    const list = screen.getByRole("list");
    expect(within(list).getAllByRole("listitem")).toHaveLength(6);
    expect(within(list).getByText("Dental Clinics")).toBeInTheDocument();
    expect(within(list).getByText("Professional Services")).toBeInTheDocument();
  });

  it("puts the scenario selector in the hero as a named group of four radios", () => {
    render(<Hero />);

    const group = screen.getByRole("group", { name: /choose a demo scenario/i });
    const radios = within(group).getAllByRole("radio");
    expect(radios).toHaveLength(4);
    expect(radios.filter((r) => (r as HTMLInputElement).checked)).toHaveLength(1);
  });

  it("stages the orchestration demo beside the copy, with one accessible summary", () => {
    render(<Hero />);

    expect(screen.getByRole("group", { name: /four.*systems/i })).toBeInTheDocument();
  });

  it("swaps the staged scenario when a different chip is chosen", async () => {
    const user = userEvent.setup();
    render(<Hero />);

    await user.click(screen.getByRole("radio", { name: /escalation/i }));

    expect(
      screen.getByRole("group", { name: /speak with your team about an urgent issue/i }),
    ).toBeInTheDocument();
  });

  // T1.1 — the headline is the LCP element. Rendering it at opacity 0 means no
  // copy is readable until JavaScript has loaded and hydrated, and defers LCP
  // behind the bundle. This asserts the server HTML, not the hydrated DOM,
  // because that is the state a visitor sees first.
  it("server-renders the headline and lede visibly, without opacity gating", () => {
    const html = renderToString(<Hero />);

    const h1 = html.match(/<h1[^>]*>/)?.[0] ?? "";
    expect(h1).not.toMatch(/opacity:\s*0[^.]/);

    // Anything that does start hidden must carry data-reveal, which the
    // <noscript> rule in app/layout.tsx targets.
    const hidden = html.match(/<[a-z0-9]+[^>]*style="[^"]*opacity:0[^"]*"[^>]*>/g) ?? [];
    const contentHidden = hidden.filter(
      (tag) => !tag.includes("data-reveal") && !tag.includes('aria-hidden="true"'),
    );
    expect(contentHidden).toEqual([]);
  });

  it("renders a static, fully resolved stage for prefers-reduced-motion", () => {
    mockReducedMotion(true);
    render(<Hero />);

    expect(screen.getByRole("img", { name: /four.*systems/i })).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: /four.*systems/i })).toBeNull();
  });
});
