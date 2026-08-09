import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Reveal } from "./reveal";

describe("Reveal", () => {
  it("renders its children (visible immediately without IntersectionObserver, e.g. in tests)", () => {
    render(<Reveal>Section content</Reveal>);
    expect(screen.getByText("Section content")).toBeInTheDocument();
  });
});
