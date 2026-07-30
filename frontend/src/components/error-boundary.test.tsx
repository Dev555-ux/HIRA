import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ErrorBoundary } from "./error-boundary";

function Throws(): ReactNode {
  throw new Error("Render failed");
}

describe("ErrorBoundary", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("recovers when the route reset key changes", () => {
    const { rerender } = render(
      <ErrorBoundary resetKey="/dashboard">
        <Throws />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();

    rerender(
      <ErrorBoundary resetKey="/customers">
        <p>Customers loaded</p>
      </ErrorBoundary>,
    );

    expect(screen.getByText("Customers loaded")).toBeInTheDocument();
  });
});
