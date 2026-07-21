import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SectionHeader } from "./section-header";

describe("SectionHeader", () => {
  it("renders the title as an h2", () => {
    render(<SectionHeader title="Set up in four steps" />);

    expect(screen.getByRole("heading", { level: 2, name: "Set up in four steps" })).toBeInTheDocument();
  });

  it("omits the description paragraph when none is given", () => {
    const { container } = render(<SectionHeader title="Frequently asked questions" />);

    expect(container.querySelector("p")).toBeNull();
  });

  it("renders the description when given, using the shared supporting-paragraph size", () => {
    render(<SectionHeader title="One employee, not a bundle of bots" description="A single AI agent holds it together." />);

    const description = screen.getByText("A single AI agent holds it together.");
    expect(description).toHaveClass("text-lg");
  });

  it("merges a caller-provided className onto the wrapper without losing text-center", () => {
    const { container } = render(<SectionHeader title="Everything the front desk does, minus the wait" className="mx-auto max-w-2xl" />);

    const wrapper = container.firstChild;
    expect(wrapper).toHaveClass("text-center");
    expect(wrapper).toHaveClass("mx-auto");
    expect(wrapper).toHaveClass("max-w-2xl");
  });
});
