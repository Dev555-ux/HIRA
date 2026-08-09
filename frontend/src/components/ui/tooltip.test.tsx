import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Button } from "./button";
import { Tooltip } from "./tooltip";

describe("Tooltip", () => {
  it("shows its content on focus and hides on blur", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Approve this reply">
        <Button>Approve</Button>
      </Tooltip>,
    );

    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    await user.tab();
    expect(screen.getByRole("button")).toHaveFocus();
    expect(screen.getByRole("tooltip")).toHaveTextContent("Approve this reply");

    await user.tab();
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("associates the tooltip with the trigger via aria-describedby", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Explains the control">
        <Button>Info</Button>
      </Tooltip>,
    );
    await user.tab();
    const button = screen.getByRole("button");
    const tooltip = screen.getByRole("tooltip");
    expect(button).toHaveAttribute("aria-describedby", tooltip.id);
  });
});
