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

const CREATED_BUSINESS = {
  id: "biz-1",
  name: "Acme Dental Clinic",
  industry: "Dental Clinic",
  contact_email: "hello@acme.com",
  country: null,
  timezone: "UTC",
  onboarding_status: "created" as const,
  whatsapp_connection_status: "not_connected" as const,
};

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
    // Harmless default for tests that never submit — the component now
    // calls useOnboardingStatus() on mount too (to get a `refetch` it can
    // use after a successful submit), so this must always resolve to
    // something valid even when a given test doesn't care about its value.
    vi.mocked(api.getOnboardingStatus).mockResolvedValue({ has_business: false, business: null });
    // Sprint 72: pin the auto-detected timezone to a known value rather
    // than relying on whatever the test environment's ambient TZ happens
    // to be — real detection logic is exercised, the assertion just isn't
    // environment-dependent.
    vi.spyOn(Intl, "DateTimeFormat").mockReturnValue({
      resolvedOptions: () => ({ timeZone: "Asia/Kolkata" }),
    } as Intl.DateTimeFormat);
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

  it("submits the business, confirms provisioning, and redirects to the dashboard", async () => {
    const user = userEvent.setup();
    vi.mocked(api.createBusiness).mockResolvedValue(CREATED_BUSINESS);
    // FTUE-1: navigation now waits on this confirming has_business: true —
    // not just on createBusiness's own response.
    vi.mocked(api.getOnboardingStatus).mockResolvedValue({
      has_business: true,
      business: CREATED_BUSINESS,
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
        // Sprint 72: no longer undefined — auto-detected on mount (see the
        // dedicated timezone describe block below for the detection itself).
        timezone: "Asia/Kolkata",
      }),
    );
    await waitFor(() => expect(api.getOnboardingStatus).toHaveBeenCalled());
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
    expect(screen.getByText("You're all set!")).toBeInTheDocument();
  });

  it("does not navigate to the dashboard if provisioning can't be confirmed after creating the business", async () => {
    const user = userEvent.setup();
    vi.mocked(api.createBusiness).mockResolvedValue(CREATED_BUSINESS);
    // The POST itself succeeded, but a re-check still reports no business —
    // this must not be trusted as "done."
    vi.mocked(api.getOnboardingStatus).mockResolvedValue({ has_business: false, business: null });

    renderWithProviders(<OnboardingPage />);

    await user.type(screen.getByPlaceholderText("Acme Dental Clinic"), "Acme Dental Clinic");
    await user.selectOptions(screen.getByRole("combobox"), "Dental Clinic");
    await user.type(screen.getByPlaceholderText("hello@acmedental.com"), "hello@acme.com");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(
      await screen.findByText("We couldn't confirm your account is ready yet — please try again."),
    ).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
    expect(screen.queryByText("You're all set!")).not.toBeInTheDocument();
  });

  it("blocks submission and explains when the account has no email", () => {
    renderWithProviders(<OnboardingPage />, {
      ...mockAuth,
      user: { name: "Dev User", email: "", imageUrl: null },
    });

    expect(screen.getByText(/couldn't find a verified email/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /continue/i })).toBeDisabled();
  });

  describe("timezone auto-detect (Sprint 72)", () => {
    it("prefills the timezone field from the browser's own timezone", async () => {
      renderWithProviders(<OnboardingPage />);

      await waitFor(() =>
        expect(screen.getByPlaceholderText("Asia/Kolkata")).toHaveValue("Asia/Kolkata"),
      );
    });

    it("stays editable — a manual change overrides the detected value", async () => {
      const user = userEvent.setup();
      vi.mocked(api.createBusiness).mockResolvedValue(CREATED_BUSINESS);
      vi.mocked(api.getOnboardingStatus).mockResolvedValue({
        has_business: true,
        business: CREATED_BUSINESS,
      });
      renderWithProviders(<OnboardingPage />);

      const timezoneField = screen.getByPlaceholderText("Asia/Kolkata");
      await waitFor(() => expect(timezoneField).toHaveValue("Asia/Kolkata"));
      await user.clear(timezoneField);
      await user.type(timezoneField, "America/Chicago");

      await user.type(screen.getByPlaceholderText("Acme Dental Clinic"), "Acme Dental Clinic");
      await user.selectOptions(screen.getByRole("combobox"), "Dental Clinic");
      await user.type(screen.getByPlaceholderText("hello@acmedental.com"), "hello@acme.com");
      await user.click(screen.getByRole("button", { name: /continue/i }));

      await waitFor(() =>
        expect(api.createBusiness).toHaveBeenCalledWith(
          expect.any(Function),
          expect.objectContaining({ timezone: "America/Chicago" }),
        ),
      );
    });
  });
});
