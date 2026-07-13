import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DashboardHero } from "./dashboard-hero";

describe("DashboardHero", () => {
  it("renders the owner's name and the given summary sentence", async () => {
    render(
      <DashboardHero
        name="Dev"
        summary="You have 2 replies waiting for review and 1 appointment booked."
        isRefreshing={false}
        onRefresh={vi.fn()}
      />,
    );

    // Starts as "Welcome back" (pre-hydration-safe) and switches to a
    // time-of-day greeting once mounted — assert the name renders under
    // either, rather than pinning down a specific hour-dependent string.
    const heading = await screen.findByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Dev");
    expect(
      screen.getByText("You have 2 replies waiting for review and 1 appointment booked."),
    ).toBeInTheDocument();
  });

  it("renders exactly one h1", () => {
    render(
      <DashboardHero name="Dev" summary="Summary." isRefreshing={false} onRefresh={vi.fn()} />,
    );
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("calls onRefresh when Refresh is clicked, and spins the icon while refreshing", () => {
    const onRefresh = vi.fn();
    const { rerender, container } = render(
      <DashboardHero name="Dev" summary="Summary." isRefreshing={false} onRefresh={onRefresh} />,
    );

    screen.getByRole("button", { name: /refresh/i }).click();
    expect(onRefresh).toHaveBeenCalledTimes(1);
    expect(container.querySelector(".animate-spin")).not.toBeInTheDocument();

    rerender(
      <DashboardHero name="Dev" summary="Summary." isRefreshing={true} onRefresh={onRefresh} />,
    );
    expect(container.querySelector(".animate-spin")).toBeInTheDocument();
  });

  it("links Test AI to the Playground", async () => {
    const user = userEvent.setup();
    render(
      <DashboardHero name="Dev" summary="Summary." isRefreshing={false} onRefresh={vi.fn()} />,
    );

    const link = screen.getByRole("link", { name: /test ai/i });
    expect(link).toHaveAttribute("href", "/playground");
    await user.tab();
  });
});
