import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/toast";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import OnboardingPage from "./page";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: { createBusiness: vi.fn(), getOnboardingStatus: vi.fn() },
}));

import { api } from "@/lib/api";

const mockAuth: AuthContextValue = {
  getToken: async () => "test-token",
  user: { name: "Dev User", email: "owner@acme.com", imageUrl: null },
  isLoaded: true,
  mocked: true,
  signOut: vi.fn(),
  openProfile: vi.fn(),
};

function renderWithProviders(ui: React.ReactElement, auth: AuthContextValue = mockAuth) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={auth}>
        <ToastProvider>{ui}</ToastProvider>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

describe("OnboardingPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows validation errors when required fields are missing", async () => {
    const user = userEvent.setup();
    renderWithProviders(<OnboardingPage />);

    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(await screen.findByText("Business name is required")).toBeInTheDocument();
    expect(screen.getByText("Select what kind of business this is")).toBeInTheDocument();
    expect(screen.getByText("Business email is required")).toBeInTheDocument();
    expect(api.createBusiness).not.toHaveBeenCalled();
  });

  it("submits the business and redirects to the dashboard", async () => {
    const user = userEvent.setup();
    vi.mocked(api.createBusiness).mockResolvedValue({
      id: "biz-1",
      name: "Acme Dental Clinic",
      industry: "Dental Clinic",
      contact_email: "hello@acme.com",
      country: null,
      timezone: "UTC",
      onboarding_status: "created",
      whatsapp_connection_status: "not_connected",
    });

    renderWithProviders(<OnboardingPage />);

    await user.type(screen.getByPlaceholderText("Acme Dental Clinic"), "Acme Dental Clinic");
    await user.selectOptions(screen.getByRole("combobox"), "Dental Clinic");
    await user.type(screen.getByPlaceholderText("hello@acmedental.com"), "hello@acme.com");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() =>
      expect(api.createBusiness).toHaveBeenCalledWith(expect.any(Function), {
        name: "Acme Dental Clinic",
        owner_email: "owner@acme.com",
        industry: "Dental Clinic",
        contact_email: "hello@acme.com",
        country: undefined,
        timezone: undefined,
      }),
    );
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
    expect(screen.getByText("You're all set!")).toBeInTheDocument();
  });

  it("blocks submission and explains when the account has no email", () => {
    renderWithProviders(<OnboardingPage />, {
      ...mockAuth,
      user: { name: "Dev User", email: "", imageUrl: null },
    });

    expect(screen.getByText(/couldn't find a verified email/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /continue/i })).toBeDisabled();
  });
});
