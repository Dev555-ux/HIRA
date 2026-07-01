import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import PendingPage from "./page";

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: { listPending: vi.fn(), approveMessage: vi.fn() },
}));

import { api } from "@/lib/api";

const mockAuth: AuthContextValue = {
  getToken: async () => "test-token",
  user: null,
  isLoaded: true,
  mocked: true,
};

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={mockAuth}>{ui}</AuthContext.Provider>
    </QueryClientProvider>,
  );
}

describe("PendingPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows the empty state when there are no pending replies", async () => {
    vi.mocked(api.listPending).mockResolvedValue([]);
    renderWithProviders(<PendingPage />);
    await waitFor(() =>
      expect(screen.getByText("All caught up")).toBeInTheDocument(),
    );
  });

  it("renders a pending reply with an approve action", async () => {
    vi.mocked(api.listPending).mockResolvedValue([
      {
        id: "1",
        conversation_id: "c1",
        body: "We are open 9am to 5pm.",
        created_at: new Date().toISOString(),
      },
    ]);
    renderWithProviders(<PendingPage />);
    await waitFor(() =>
      expect(screen.getByText("We are open 9am to 5pm.")).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: /approve/i }),
    ).toBeInTheDocument();
  });
});
