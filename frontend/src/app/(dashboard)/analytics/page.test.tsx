import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import AnalyticsPage from "./page";

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: { listPending: vi.fn(), listConversations: vi.fn() },
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
    vi.mocked(api.listConversations).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 1, offset: 0 },
    });
  });

  it("does not render a fabricated chart", async () => {
    const { container } = renderWithProviders(<AnalyticsPage />);
    await screen.findAllByText("Analytics coming soon");
    // The old implementation rendered fake bars as bg-muted divs with inline
    // height styles — assert that fabricated-data pattern is gone.
    expect(container.querySelectorAll("[style*='height']").length).toBe(0);
    expect(screen.queryByText(/placeholder chart/i)).not.toBeInTheDocument();
  });

  it("shows an honest empty state for each chart instead", async () => {
    renderWithProviders(<AnalyticsPage />);
    expect(await screen.findAllByText("Analytics coming soon")).toHaveLength(2);
  });

  it("shows the real conversation total instead of a fake 'Coming soon' (Sprint 35 fix)", async () => {
    vi.mocked(api.listConversations).mockResolvedValue({
      data: [],
      meta: { total: 42, limit: 1, offset: 0 },
    });
    renderWithProviders(<AnalyticsPage />);

    expect(await screen.findByText("42")).toBeInTheDocument();
    expect(api.listConversations).toHaveBeenCalledWith(
      expect.any(Function),
      expect.objectContaining({ limit: 1 }),
    );
  });

  it("shows a dash instead of a misleading zero when the total fails to load", async () => {
    vi.mocked(api.listConversations).mockRejectedValue(new Error("Network error"));
    renderWithProviders(<AnalyticsPage />);

    // "Couldn't load" only appears once the conversations query has actually
    // settled into its error state — wait for that before counting dashes.
    await screen.findByText("Couldn't load");
    // "Messages today"/"Avg response time" also permanently show "—" — three
    // total once the conversations tile joins them on error.
    expect(screen.getAllByText("—")).toHaveLength(3);
  });
});
