import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TaskCard } from "./task-card";

describe("TaskCard", () => {
  it("renders title, description, and meta", () => {
    render(<TaskCard title="Confirm Thursday's booking" description="Customer asked to move to 6pm" meta="Due today" />);
    expect(screen.getByText("Confirm Thursday's booking")).toBeInTheDocument();
    expect(screen.getByText("Customer asked to move to 6pm")).toBeInTheDocument();
    expect(screen.getByText("Due today")).toBeInTheDocument();
  });

  it("fires the action handler", async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();
    render(<TaskCard title="Task" action={{ label: "Resolve", onClick }} />);
    await user.click(screen.getByRole("button", { name: "Resolve" }));
    expect(onClick).toHaveBeenCalledOnce();
  });
});
