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
});
