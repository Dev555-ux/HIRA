import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import type { OnboardingStatus } from "@/lib/types";
import DashboardPage from "./page";

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: {
    listPending: vi.fn(),
    getOnboardingStatus: vi.fn(),
    listConversations: vi.fn(),
    listCustomers: vi.fn(),
  },
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

const onboardingStatus: OnboardingStatus = {
  has_business: true,
  business: {
    id: "biz-1",
    name: "Stoneveil Dental",
    onboarding_status: "live",
    whatsapp_connection_status: "connected",
  } as OnboardingStatus["business"],
};

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={mockAuth}>{ui}</AuthContext.Provider>
    </QueryClientProvider>,
  );
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getOnboardingStatus).mockResolvedValue(onboardingStatus);
  });

  it("shows real conversation and customer totals from existing list endpoints", async () => {
    vi.mocked(api.listPending).mockResolvedValue([]);
    vi.mocked(api.listConversations).mockResolvedValue({
      data: [],
      meta: { total: 37, limit: 1, offset: 0 },
    });
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [],
      meta: { total: 12, limit: 1, offset: 0 },
    });

    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("37")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(api.listConversations).toHaveBeenCalledWith(
      expect.any(Function),
      expect.objectContaining({ limit: 1 }),
    );
    expect(api.listCustomers).toHaveBeenCalledWith(
      expect.any(Function),
      expect.objectContaining({ limit: 1 }),
    );
  });

  it("shows the pending-approval count", async () => {
    vi.mocked(api.listPending).mockResolvedValue([
      {
        id: "msg-1",
        conversation_id: "conv-1",
        body: "Yes, we're open!",
        created_at: new Date().toISOString(),
        customer: null,
        conversation_preview: null,
      },
    ]);
    vi.mocked(api.listConversations).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 1, offset: 0 },
    });
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 1, offset: 0 },
    });

    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("Yes, we're open!")).toBeInTheDocument();
  });
});
