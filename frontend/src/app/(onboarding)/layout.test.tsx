import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import OnboardingLayout from "./layout";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api", () => ({
  api: { getOnboardingStatus: vi.fn() },
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

// Mirrors (dashboard)/layout.test.tsx's cold-start helper — isLoaded starts
// false (query disabled) and flips true a tick later, the exact window the
// isPending-vs-isLoading bug lived in.
function renderWithColdAuth(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  function ColdAuthProvider({ children }: { children: React.ReactNode }) {
    const [isLoaded, setIsLoaded] = useState(false);
    return (
      <AuthContext.Provider value={{ ...mockAuth, isLoaded }}>
        <button onClick={() => setIsLoaded(true)}>finish loading clerk</button>
        {children}
      </AuthContext.Provider>
    );
  }

  return render(
    <QueryClientProvider client={qc}>
      <ColdAuthProvider>{ui}</ColdAuthProvider>
    </QueryClientProvider>,
  );
}

describe("OnboardingLayout", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders the onboarding form when the user has no business yet", async () => {
    vi.mocked(api.getOnboardingStatus).mockResolvedValue({ has_business: false, business: null });

    renderWithProviders(<OnboardingLayout>the form</OnboardingLayout>);

    await waitFor(() => expect(screen.getByText("the form")).toBeInTheDocument());
    expect(replace).not.toHaveBeenCalled();
  });

  it("redirects to /dashboard once a business already exists", async () => {
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

    renderWithProviders(<OnboardingLayout>the form</OnboardingLayout>);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
    expect(screen.queryByText("the form")).not.toBeInTheDocument();
  });

  it("never flashes the onboarding form for an already-onboarded account while Clerk is still loading", async () => {
    // Same regression this bug caused in (dashboard)/layout.tsx, mirrored
    // here: isPending (not isLoading) must gate this skeleton too, or a
    // cold page load briefly renders the real form for a user who already
    // has a business, before their status has actually loaded.
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
    const user = userEvent.setup();

    renderWithColdAuth(<OnboardingLayout>the form</OnboardingLayout>);

    expect(screen.queryByText("the form")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "finish loading clerk" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
    expect(screen.queryByText("the form")).not.toBeInTheDocument();
  });
});
