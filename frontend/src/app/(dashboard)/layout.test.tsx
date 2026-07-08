import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import DashboardLayout from "./layout";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/dashboard",
}));

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: { getOnboardingStatus: vi.fn(), listPending: vi.fn() },
}));

import { api } from "@/lib/api";

const mockAuth: AuthContextValue = {
  getToken: async () => "test-token",
  user: { name: "Dev User", email: "dev@hira.local", imageUrl: null },
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

describe("DashboardLayout", () => {
  beforeEach(() => vi.clearAllMocks());

  it("redirects to /onboarding when the user has no business", async () => {
    vi.mocked(api.getOnboardingStatus).mockResolvedValue({ has_business: false, business: null });

    renderWithProviders(<DashboardLayout>content</DashboardLayout>);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/onboarding"));
    expect(screen.queryByText("content")).not.toBeInTheDocument();
  });

  it("renders the dashboard chrome once a business exists", async () => {
    vi.mocked(api.getOnboardingStatus).mockResolvedValue({
      has_business: true,
      business: {
        id: "biz-1",
        name: "Acme",
        industry: null,
        contact_email: null,
        country: null,
        timezone: "UTC",
        onboarding_status: "created",
        whatsapp_connection_status: "not_connected",
      },
    });

    renderWithProviders(<DashboardLayout>content</DashboardLayout>);

    await waitFor(() => expect(screen.getByText("content")).toBeInTheDocument());
    expect(replace).not.toHaveBeenCalled();
  });
});
