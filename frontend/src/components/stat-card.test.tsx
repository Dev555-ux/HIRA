import { render, screen } from "@testing-library/react";
import { CheckCheck } from "lucide-react";
import { describe, expect, it } from "vitest";
import { StatCard } from "./stat-card";

describe("StatCard", () => {
  it("shows a skeleton instead of the value while loading, with no fade-in yet", () => {
    const { container } = render(
      <StatCard label="Pending approvals" value={3} icon={CheckCheck} loading />,
    );
    expect(screen.queryByText("3")).not.toBeInTheDocument();
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("fades the value in once loaded, and never animates the number itself beyond that", () => {
    render(<StatCard label="Pending approvals" value={3} icon={CheckCheck} hint="Awaiting your review" />);

    const value = screen.getByText("3");
    expect(value).toHaveClass("animate-fade-in");
    // The entrance is a plain opacity fade — no count-up, no transform on the
    // number itself (only the card as a whole gets a hover transform).
    expect(value.className).not.toMatch(/translate|scale/);
  });

  it("renders the label and hint", () => {
    render(
      <StatCard
        label="Pending approvals"
        value={0}
        icon={CheckCheck}
        hint="Everything reviewed"
      />,
    );
    expect(screen.getByText("Pending approvals")).toBeInTheDocument();
    expect(screen.getByText("Everything reviewed")).toBeInTheDocument();
  });
});
