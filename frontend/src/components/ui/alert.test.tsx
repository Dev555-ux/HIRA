import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Alert } from "./alert";

describe("Alert", () => {
  it("renders a title and description", () => {
    render(<Alert title="Heads up">Something you should know.</Alert>);
    expect(screen.getByText("Heads up")).toBeInTheDocument();
    expect(screen.getByText("Something you should know.")).toBeInTheDocument();
  });

  it("uses role=alert for destructive and warning, role=status otherwise", () => {
    const { rerender } = render(<Alert variant="destructive">Failed</Alert>);
    expect(screen.getByRole("alert")).toBeInTheDocument();

    rerender(<Alert variant="success">Done</Alert>);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
