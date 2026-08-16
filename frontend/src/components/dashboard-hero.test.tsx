import { CheckCheck } from "lucide-react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DashboardHero } from "./dashboard-hero";

describe("DashboardHero", () => {
  it("renders the owner's name and the given summary sentence", async () => {
    render(
      <DashboardHero
        name="Dev"
        summary="Here's what's happening with your business."
        isRefreshing={false}
        onRefresh={vi.fn()}
        roster={[]}
      />,
    );

    // Starts as "Welcome back" (pre-hydration-safe) and switches to a
    // time-of-day greeting once mounted — assert the name renders under
    // either, rather than pinning down a specific hour-dependent string.
    const heading = await screen.findByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Dev");
    expect(screen.getByText("Here's what's happening with your business.")).toBeInTheDocument();
  });

  it("greets with the first name only, not the full name", async () => {
    render(
      <DashboardHero
        name="Jordan A. Whitfield-Smith"
        summary="Summary."
        isRefreshing={false}
        onRefresh={vi.fn()}
        roster={[]}
      />,
    );
    const heading = await screen.findByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Jordan");
    expect(heading).not.toHaveTextContent("Whitfield-Smith");
  });

  it("applies the one-time entrance animation to its root, not to anything that re-renders on its own", () => {
    const { container } = render(
      <DashboardHero name="Dev" summary="Summary." isRefreshing={false} onRefresh={vi.fn()} roster={[]} />,
    );
    expect(container.querySelector(".animate-fade-in-up")).toBeInTheDocument();
  });

  it("renders exactly one h1", () => {
    render(
      <DashboardHero name="Dev" summary="Summary." isRefreshing={false} onRefresh={vi.fn()} roster={[]} />,
    );
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("calls onRefresh when Refresh is clicked, and spins the icon while refreshing", () => {
    const onRefresh = vi.fn();
    const { rerender, container } = render(
      <DashboardHero name="Dev" summary="Summary." isRefreshing={false} onRefresh={onRefresh} roster={[]} />,
    );

    screen.getByRole("button", { name: /refresh/i }).click();
    expect(onRefresh).toHaveBeenCalledTimes(1);
    expect(container.querySelector(".animate-spin")).not.toBeInTheDocument();

    rerender(
      <DashboardHero name="Dev" summary="Summary." isRefreshing={true} onRefresh={onRefresh} roster={[]} />,
    );
    expect(container.querySelector(".animate-spin")).toBeInTheDocument();
  });

  it("links Test AI to Demo Chat", async () => {
    const user = userEvent.setup();
    render(
      <DashboardHero name="Dev" summary="Summary." isRefreshing={false} onRefresh={vi.fn()} roster={[]} />,
    );

    const link = screen.getByRole("link", { name: /test ai/i });
    expect(link).toHaveAttribute("href", "/demo");
    await user.tab();
  });

  it("has no promoted review CTA when pendingCount is 0 or omitted", () => {
    render(
      <DashboardHero name="Dev" summary="Summary." isRefreshing={false} onRefresh={vi.fn()} roster={[]} />,
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
        roster={[]}
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
        roster={[]}
      />,
    );
    expect(screen.getByRole("link", { name: /review 4 replies/i })).toHaveAttribute(
      "href",
      "/pending",
    );
  });

  it("renders real highlights as a checklist instead of the flat summary sentence", () => {
    render(
      <DashboardHero
        name="Dev"
        summary="Summary."
        highlights={[{ icon: CheckCheck, label: "Answered 3 customer messages" }]}
        isRefreshing={false}
        onRefresh={vi.fn()}
        roster={[]}
      />,
    );
    expect(screen.getByText("Answered 3 customer messages")).toBeInTheDocument();
    expect(screen.queryByText("Summary.")).not.toBeInTheDocument();
  });

  it("falls back to the flat summary sentence when there are no real highlights", () => {
    render(
      <DashboardHero
        name="Dev"
        summary="Summary."
        highlights={[]}
        isRefreshing={false}
        onRefresh={vi.fn()}
        roster={[]}
      />,
    );
    expect(screen.getByText("Summary.")).toBeInTheDocument();
  });

  it("shows the reassuring close only when nothing needs attention", () => {
    const { rerender } = render(
      <DashboardHero
        name="Dev"
        summary="Summary."
        needsAttention={false}
        isRefreshing={false}
        onRefresh={vi.fn()}
        roster={[]}
      />,
    );
    expect(screen.getByText("Nothing urgent requires you.")).toBeInTheDocument();

    rerender(
      <DashboardHero
        name="Dev"
        summary="Summary."
        needsAttention={true}
        isRefreshing={false}
        onRefresh={vi.fn()}
        roster={[]}
      />,
    );
    expect(screen.queryByText("Nothing urgent requires you.")).not.toBeInTheDocument();
  });

  it("shows the AI Network for every real employee role, active or idle", () => {
    render(
      <DashboardHero
        name="Dev"
        summary="Summary."
        isRefreshing={false}
        onRefresh={vi.fn()}
        roster={[
          { role: "scheduler", count: 5, pct: 100, mostActive: true, active: true },
          { role: "bookkeeper", count: 0, pct: 0, mostActive: false, active: false },
        ]}
      />,
    );
    expect(screen.getByText("Scheduler")).toBeInTheDocument();
    expect(screen.getByText("Bookkeeper")).toBeInTheDocument();
  });
});
