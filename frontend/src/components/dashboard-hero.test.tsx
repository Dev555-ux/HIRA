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

  it("greets with the first name only, not the full name", async () => {
    render(
      <DashboardHero
        name="Jordan A. Whitfield-Smith"
        summary="Summary."
        isRefreshing={false}
        onRefresh={vi.fn()}
      />,
    );
    const heading = await screen.findByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Jordan");
    expect(heading).not.toHaveTextContent("Whitfield-Smith");
  });

  it("applies the one-time entrance animation to its root, not to anything that re-renders on its own", () => {
    const { container } = render(
      <DashboardHero name="Dev" summary="Summary." isRefreshing={false} onRefresh={vi.fn()} />,
    );
    expect(container.querySelector(".animate-fade-in-up")).toBeInTheDocument();
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

  it("links Test AI to Demo Chat", async () => {
    const user = userEvent.setup();
    render(
      <DashboardHero name="Dev" summary="Summary." isRefreshing={false} onRefresh={vi.fn()} />,
    );

    const link = screen.getByRole("link", { name: /test ai/i });
    expect(link).toHaveAttribute("href", "/demo");
    await user.tab();
  });

  it("has no promoted review CTA when pendingCount is 0 or omitted", () => {
    render(
      <DashboardHero name="Dev" summary="Summary." isRefreshing={false} onRefresh={vi.fn()} />,
    );
    expect(screen.queryByRole("link", { name: /review/i })).not.toBeInTheDocument();
  });

  it("promotes a singular 'Review 1 reply' CTA to /pending when pendingCount is 1", () => {
    render(
      <DashboardHero
        name="Dev"
        summary="Summary."
        isRefreshing={false}
        onRefresh={vi.fn()}
        pendingCount={1}
      />,
    );
    const link = screen.getByRole("link", { name: /review 1 reply/i });
    expect(link).toHaveAttribute("href", "/pending");
    expect(link).not.toHaveTextContent("replies");
  });

  it("promotes a plural 'Review N replies' CTA when pendingCount is many", () => {
    render(
      <DashboardHero
        name="Dev"
        summary="Summary."
        isRefreshing={false}
        onRefresh={vi.fn()}
        pendingCount={4}
      />,
    );
    expect(screen.getByRole("link", { name: /review 4 replies/i })).toHaveAttribute(
      "href",
      "/pending",
    );
  });
});
