import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";
import DashboardLayout from "./layout";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/dashboard",
}));

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
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

  it("redirects to /onboarding when the user has no business, and never renders dashboard content meanwhile", async () => {
    vi.mocked(api.getOnboardingStatus).mockResolvedValue({ has_business: false, business: null });

    renderWithProviders(<DashboardLayout>content</DashboardLayout>);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/onboarding"));
    expect(screen.queryByText("content")).not.toBeInTheDocument();
    // FTUE-1: an explicit, friendly state instead of silently rendering
    // nothing (or the dashboard) while the redirect is in flight.
    expect(screen.getByText("Welcome to HIRA")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Continue Setup" })).toHaveAttribute(
      "href",
      "/onboarding",
    );
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

  it("never falls open to dashboard content when the status check fails for a non-auth reason", async () => {
    vi.mocked(api.getOnboardingStatus).mockRejectedValue(new Error("network blip"));

    renderWithProviders(<DashboardLayout>content</DashboardLayout>);

    expect(await screen.findByText("Couldn't verify your account")).toBeInTheDocument();
    expect(screen.queryByText("content")).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("recovers from a failed status check when Retry succeeds", async () => {
    vi.mocked(api.getOnboardingStatus)
      .mockRejectedValueOnce(new Error("network blip"))
      .mockResolvedValueOnce({
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
    const user = userEvent.setup();

    renderWithProviders(<DashboardLayout>content</DashboardLayout>);

    await screen.findByText("Couldn't verify your account");
    await user.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(screen.getByText("content")).toBeInTheDocument());
  });

  it("treats a 401 from the status check as a real authentication failure, never as 'needs onboarding'", async () => {
    vi.mocked(api.getOnboardingStatus).mockRejectedValue(new ApiError(401, "Invalid authentication token"));

    renderWithProviders(<DashboardLayout>content</DashboardLayout>);

    expect(await screen.findByText("Your session has expired")).toBeInTheDocument();
    expect(screen.queryByText("content")).not.toBeInTheDocument();
    expect(screen.queryByText("Welcome to HIRA")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/sign-in");
  });
});
