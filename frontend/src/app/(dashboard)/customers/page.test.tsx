import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import CustomersPage from "./page";

describe("CustomersPage", () => {
  it("disables the search control instead of pretending it works", () => {
    render(<CustomersPage />);
    expect(screen.getByPlaceholderText(/search customers/i)).toBeDisabled();
  });

  it("uses customer-friendly empty-state copy, not developer language", () => {
    render(<CustomersPage />);

    expect(screen.getByText("Customer list is coming soon")).toBeInTheDocument();
    expect(screen.queryByText(/api/i)).not.toBeInTheDocument();
  });
});
