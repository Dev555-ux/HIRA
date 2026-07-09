import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import { ToastProvider } from "@/components/ui/toast";
import SettingsPage from "./page";

function aiReplyModeCard() {
  return screen.getByText("AI Reply Mode").closest<HTMLElement>(".rounded-xl")!;
}

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: { getSettings: vi.fn(), updateSettings: vi.fn(), getOnboardingStatus: vi.fn() },
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
      <AuthContext.Provider value={mockAuth}>
        <ToastProvider>{ui}</ToastProvider>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

describe("SettingsPage — AI Reply Mode", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getOnboardingStatus).mockResolvedValue({ has_business: false, business: null });
  });

  it("selects the current mode once settings load", async () => {
    vi.mocked(api.getSettings).mockResolvedValue({ mode: "assisted" });
    renderWithProviders(<SettingsPage />);

    await waitFor(() =>
      expect(screen.getByRole("radio", { name: /assisted/i })).toBeChecked(),
    );
    expect(screen.getByRole("radio", { name: /autonomous/i })).not.toBeChecked();
  });

  it("disables Save until the mode is changed", async () => {
    vi.mocked(api.getSettings).mockResolvedValue({ mode: "assisted" });
    renderWithProviders(<SettingsPage />);

    await waitFor(() =>
      expect(screen.getByRole("radio", { name: /assisted/i })).toBeChecked(),
    );
    expect(within(aiReplyModeCard()).getByRole("button", { name: /save/i })).toBeDisabled();
  });

  it("saves the new mode, shows a success toast, and disables controls while saving", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getSettings).mockResolvedValue({ mode: "assisted" });
    let resolveUpdate: (value: { mode: "autonomous" }) => void;
    vi.mocked(api.updateSettings).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveUpdate = resolve;
        }),
    );

    renderWithProviders(<SettingsPage />);

    await waitFor(() =>
      expect(screen.getByRole("radio", { name: /assisted/i })).toBeChecked(),
    );

    await user.click(screen.getByRole("radio", { name: /autonomous/i }));
    const saveButton = within(aiReplyModeCard()).getByRole("button", { name: /save/i });
    expect(saveButton).not.toBeDisabled();

    await user.click(saveButton);

    await waitFor(() => expect(saveButton).toBeDisabled());
    expect(screen.getByRole("radio", { name: /assisted/i })).toBeDisabled();
    expect(screen.getByRole("radio", { name: /autonomous/i })).toBeDisabled();

    resolveUpdate!({ mode: "autonomous" });

    await waitFor(() =>
      expect(screen.getByText("Settings saved")).toBeInTheDocument(),
    );
    expect(api.updateSettings).toHaveBeenCalledWith(expect.any(Function), {
      mode: "autonomous",
    });
  });

  it("shows a destructive toast when saving fails", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getSettings).mockResolvedValue({ mode: "assisted" });
    vi.mocked(api.updateSettings).mockRejectedValue(new Error("Network error"));

    renderWithProviders(<SettingsPage />);

    await waitFor(() =>
      expect(screen.getByRole("radio", { name: /assisted/i })).toBeChecked(),
    );
    await user.click(screen.getByRole("radio", { name: /autonomous/i }));
    await user.click(within(aiReplyModeCard()).getByRole("button", { name: /save/i }));

    await waitFor(() =>
      expect(screen.getByText("Couldn't save settings")).toBeInTheDocument(),
    );
  });

  it("shows a retryable error state when AI Reply Mode fails to load", async () => {
    vi.mocked(api.getSettings).mockRejectedValue(new Error("Network error"));
    renderWithProviders(<SettingsPage />);

    expect(
      await within(aiReplyModeCard()).findByText("Couldn't load AI Reply Mode"),
    ).toBeInTheDocument();
    expect(within(aiReplyModeCard()).queryByRole("radiogroup")).not.toBeInTheDocument();
  });
});

describe("SettingsPage — Business information", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getSettings).mockResolvedValue({ mode: "assisted" });
  });

  it("shows the real business name, industry, and timezone read-only", async () => {
    vi.mocked(api.getOnboardingStatus).mockResolvedValue({
      has_business: true,
      business: {
        id: "biz-1",
        name: "Acme Dental Clinic",
        industry: "Dental Clinic",
        contact_email: null,
        country: null,
        timezone: "America/New_York",
        onboarding_status: "live",
        whatsapp_connection_status: "not_connected",
      },
    });

    renderWithProviders(<SettingsPage />);

    expect(await screen.findByText("Acme Dental Clinic")).toBeInTheDocument();
    expect(screen.getByText("Dental Clinic")).toBeInTheDocument();
    expect(screen.getByText("America/New_York")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /change/i })).toHaveAttribute("href", "/calendar");
  });
});
