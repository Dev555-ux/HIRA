import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import InboxPage from "./page";

describe("InboxPage", () => {
  it("disables search and filter controls instead of pretending they work", () => {
    render(<InboxPage />);

    expect(screen.getByPlaceholderText(/search conversations/i)).toBeDisabled();
    for (const label of ["All", "Pending", "Escalated", "Closed"]) {
      expect(screen.getByRole("button", { name: label })).toBeDisabled();
    }
  });

  it("uses customer-friendly empty-state copy, not developer language", () => {
    render(<InboxPage />);

    expect(screen.getByText("Inbox is coming soon")).toBeInTheDocument();
    expect(screen.queryByText(/api/i)).not.toBeInTheDocument();
  });
});
