import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AskHiraBar } from "./ask-hira-bar";

describe("AskHiraBar", () => {
  it("dispatches the same Cmd/Ctrl+K event the global command palette listens for", async () => {
    const user = userEvent.setup();
    const spy = vi.fn();
    window.addEventListener("keydown", spy);

    render(<AskHiraBar />);
    await user.click(screen.getByRole("button", { name: /ask hira/i }));

    expect(spy).toHaveBeenCalledOnce();
    const event = spy.mock.calls[0][0] as KeyboardEvent;
    expect(event.key).toBe("k");
    expect(event.metaKey || event.ctrlKey).toBe(true);
    window.removeEventListener("keydown", spy);
  });

  it("links every quick-access item to a real page — never a fabricated in-place answer", () => {
    render(<AskHiraBar />);

    const destinations: Record<string, string> = {
      "Pending approvals": "/pending",
      Escalations: "/escalations",
      Leads: "/leads",
      "Upcoming appointments": "/appointments",
    };
    for (const [label, href] of Object.entries(destinations)) {
      expect(screen.getByRole("link", { name: label })).toHaveAttribute("href", href);
    }
  });

  it("never phrases a quick link as a question — that would imply a conversational answer this doesn't deliver", () => {
    render(<AskHiraBar />);
    for (const link of screen.getAllByRole("link")) {
      expect(link.textContent).not.toMatch(/\?/);
    }
  });

  it("labels the quick links as navigation, not chat suggestions", () => {
    render(<AskHiraBar />);
    expect(screen.getByText("Jump to")).toBeInTheDocument();
  });
});
