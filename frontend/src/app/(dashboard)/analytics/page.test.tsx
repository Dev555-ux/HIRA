import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import AnalyticsPage from "./page";

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: { listPending: vi.fn() },
}));

import { api } from "@/lib/api";

const mockAuth: AuthContextValue = {
  getToken: async () => "test-token",
  user: null,
  isLoaded: true,
  mocked: true,
  signOut: vi.fn(),
  openProfile: vi.fn(),
};

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={mockAuth}>{ui}</AuthContext.Provider>
    </QueryClientProvider>,
  );
}

describe("AnalyticsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listPending).mockResolvedValue([]);
  });

  it("does not render a fabricated chart", () => {
    const { container } = renderWithProviders(<AnalyticsPage />);
    // The old implementation rendered fake bars as bg-muted divs with inline
    // height styles — assert that fabricated-data pattern is gone.
    expect(container.querySelectorAll("[style*='height']").length).toBe(0);
    expect(screen.queryByText(/placeholder chart/i)).not.toBeInTheDocument();
  });

  it("shows an honest empty state for each chart instead", () => {
    renderWithProviders(<AnalyticsPage />);
    expect(screen.getAllByText("Analytics coming soon")).toHaveLength(2);
  });
});
