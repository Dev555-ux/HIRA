import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Progress } from "./progress";

describe("Progress", () => {
  it("exposes value via ARIA", () => {
    render(<Progress value={42} label="Import progress" />);
    const bar = screen.getByRole("progressbar", { name: "Import progress" });
    expect(bar).toHaveAttribute("aria-valuenow", "42");
  });

  it("clamps out-of-range values", () => {
    render(<Progress value={140} label="Over" />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
  });
});
