import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { RecommendationCard } from "./recommendation-card";

describe("RecommendationCard", () => {
  it("renders its content and accept action", async () => {
    const onAccept = vi.fn();
    const user = userEvent.setup();
    render(
      <RecommendationCard accept={{ label: "Add to knowledge", onClick: onAccept }}>
        4 customers asked about weekend hours this week.
      </RecommendationCard>,
    );
    expect(screen.getByText(/weekend hours/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Add to knowledge" }));
    expect(onAccept).toHaveBeenCalledOnce();
  });

  it("fires onDismiss", async () => {
    const onDismiss = vi.fn();
    const user = userEvent.setup();
    render(<RecommendationCard onDismiss={onDismiss}>Suggestion text</RecommendationCard>);
    await user.click(screen.getByRole("button", { name: "Dismiss recommendation" }));
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
