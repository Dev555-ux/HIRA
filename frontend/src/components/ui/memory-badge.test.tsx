import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryBadge } from "./memory-badge";

describe("MemoryBadge", () => {
  it("defaults to a 'Learned' label", () => {
    render(<MemoryBadge />);
    expect(screen.getByText("Learned")).toBeInTheDocument();
  });

  it("renders custom content", () => {
    render(<MemoryBadge>Grounded in 3 sources</MemoryBadge>);
    expect(screen.getByText("Grounded in 3 sources")).toBeInTheDocument();
  });
});
