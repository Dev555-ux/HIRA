import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import { ToastProvider } from "@/components/ui/toast";
import type { OnboardingStatus } from "@/lib/types";
import SettingsPage from "./page";

function aiReplyModeCard() {
  return screen.getByText("How your employee responds").closest<HTMLElement>(".rounded-xl")!;
}

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: {
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
    getOnboardingStatus: vi.fn(),
    listKbEntries: vi.fn(),
    getCalendarStatus: vi.fn(),
  },
}));

const mockSearchParams = vi.fn(() => new URLSearchParams());
vi.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams(),
}));

import { api } from "@/lib/api";

const openProfile = vi.fn();

function mockAuth(overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  return {
    getToken: async () => "test-token",
    user: { name: "Dev", email: "dev@test.com", imageUrl: null },
    isLoaded: true,
    mocked: true,
    signOut: vi.fn(),
    openProfile,
    ...overrides,
  };
}

const onboardingStatus: OnboardingStatus = {
  has_business: true,
  business: {
    id: "biz-1",
    name: "Bright Smile Dental Studio",
    industry: "Dental Clinic",
    contact_email: "owner@brightsmile.test",
    country: "United States",
    timezone: "America/Chicago",
    onboarding_status: "created",
    whatsapp_connection_status: "not_connected",
  },
};

function renderWithProviders(auth: AuthContextValue = mockAuth()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={auth}>
        <ToastProvider>
          <SettingsPage />
        </ToastProvider>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchParams.mockReturnValue(new URLSearchParams());
    vi.mocked(api.getOnboardingStatus).mockResolvedValue(onboardingStatus);
    vi.mocked(api.listKbEntries).mockResolvedValue([]);
    vi.mocked(api.getCalendarStatus).mockResolvedValue({ connected: false, calendar_id: null });
    vi.mocked(api.getSettings).mockResolvedValue({ mode: "assisted" });
  });

  describe("Business profile", () => {
    it("never shows a 'coming soon' placeholder", async () => {
      renderWithProviders();
      await screen.findByText("Business profile");
      expect(screen.queryByText(/coming soon/i)).not.toBeInTheDocument();
    });

    it("shows the real business profile fields with a plain-English reason for each", async () => {
      renderWithProviders();

      expect(await screen.findByText("Bright Smile Dental Studio")).toBeInTheDocument();
      expect(screen.getByText("Dental Clinic")).toBeInTheDocument();
      expect(screen.getByText("United States")).toBeInTheDocument();
      expect(screen.getByText("owner@brightsmile.test")).toBeInTheDocument();
      // Every field explains why HIRA needs it, not just a bare value.
      expect(
        screen.getByText(/HIRA's answers are grounded in what you've taught it/i),
      ).toBeInTheDocument();
      expect(screen.getByText(/Never shared with customers/i)).toBeInTheDocument();
    });

    it("does not show Website or Logo fields (no backend data exists for either)", async () => {
      renderWithProviders();
      await screen.findByText("Business profile");
      expect(screen.queryByText("Website")).not.toBeInTheDocument();
      expect(screen.queryByText("Logo")).not.toBeInTheDocument();
    });

    it("no longer shows Timezone here — it moved to the Working hours & calendar card", async () => {
      renderWithProviders();
      const profileCard = (await screen.findByText("Business profile")).closest<HTMLElement>(
        ".rounded-xl",
      )!;
      expect(within(profileCard).queryByText("America/Chicago")).not.toBeInTheDocument();
    });
  });

  describe("Knowledge", () => {
    it("shows the real knowledge base count and links to the real page", async () => {
      vi.mocked(api.listKbEntries).mockResolvedValue([
        { id: "1", title: "Hours", content: "9-5", created_at: "", updated_at: "" },
        { id: "2", title: "Pricing", content: "$50", created_at: "", updated_at: "" },
      ]);
      renderWithProviders();

      expect(await screen.findByText("2")).toBeInTheDocument();
      expect(screen.getByText("facts taught so far")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Manage Business Knowledge" })).toHaveAttribute(
        "href",
        "/knowledge-base",
      );
    });

    it("shows an honest empty count when no knowledge has been taught yet", async () => {
      renderWithProviders();
      expect(await screen.findByText("No facts taught yet")).toBeInTheDocument();
    });
  });

  describe("Working hours & calendar", () => {
    it("shows calendar connection status and timezone, linking to the real Calendar page", async () => {
      vi.mocked(api.getCalendarStatus).mockResolvedValue({
        connected: true,
        calendar_id: "primary",
      });
      renderWithProviders();

      expect(await screen.findByText("Connected")).toBeInTheDocument();
      expect(screen.getByText("America/Chicago")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Manage calendar" })).toHaveAttribute(
        "href",
        "/calendar",
      );
    });

    it("invites connecting when Calendar isn't connected yet", async () => {
      renderWithProviders();
      expect(await screen.findByText("Not connected")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Connect Google Calendar" })).toHaveAttribute(
        "href",
        "/calendar",
      );
    });
  });

  describe("WhatsApp", () => {
    it("explains the connection in plain language instead of exposing technical fields", async () => {
      renderWithProviders();
      await screen.findByText("WhatsApp");

      expect(screen.queryByText("Phone number ID")).not.toBeInTheDocument();
      expect(screen.queryByText("Access token")).not.toBeInTheDocument();
      expect(screen.queryByText(/webhook|token|graph api|cloud api|oauth/i)).not.toBeInTheDocument();
      expect(
        screen.getByText(/customers keep messaging the number they already know/i),
      ).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Connect WhatsApp" })).toBeInTheDocument();
    });

    it("shows the reward and a test-message CTA once connected, not a dead badge", async () => {
      vi.mocked(api.getOnboardingStatus).mockResolvedValue({
        has_business: true,
        business: { ...onboardingStatus.business!, whatsapp_connection_status: "connected" },
      });
      renderWithProviders();

      expect(
        await screen.findByText(/customers can message your business through WhatsApp/i),
      ).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Send a test message" })).toHaveAttribute(
        "href",
        "/playground",
      );
    });

    it("shows business-language status, not the raw backend enum", async () => {
      vi.mocked(api.getOnboardingStatus).mockResolvedValue({
        has_business: true,
        business: {
          ...onboardingStatus.business!,
          whatsapp_connection_status: "pending_verification",
        },
      });
      renderWithProviders();

      expect(await screen.findByText("Needs attention")).toBeInTheDocument();
      expect(screen.queryByText("pending_verification")).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Continue setup" })).toBeInTheDocument();
    });

    describe("connection wizard", () => {
      function mockClipboard(writeText: (text: string) => Promise<void>) {
        Object.defineProperty(navigator, "clipboard", {
          value: { writeText },
          configurable: true,
        });
      }

      it("walks from why-connect to the request details, and copies them", async () => {
        const user = userEvent.setup();
        const writeText = vi.fn().mockResolvedValue(undefined);
        mockClipboard(writeText);
        renderWithProviders();

        await user.click(await screen.findByRole("button", { name: "Connect WhatsApp" }));
        expect(screen.getByRole("heading", { name: "Connect WhatsApp" })).toBeInTheDocument();
        expect(
          screen.getByText(/nothing changes for them/i),
        ).toBeInTheDocument();
        // No OAuth, no fake redirect — the dialog is the whole flow.
        expect(screen.queryByText(/redirecting/i)).not.toBeInTheDocument();

        await user.click(screen.getByRole("button", { name: "Continue" }));
        expect(
          screen.getByRole("heading", { name: "Your WhatsApp Business number" }),
        ).toBeInTheDocument();

        const copyButton = screen.getByRole("button", { name: /copy request details/i });
        expect(copyButton).toBeDisabled();

        await user.type(screen.getByPlaceholderText("+1 555 000 1234"), "+15550001234");
        expect(copyButton).not.toBeDisabled();

        await user.click(copyButton);
        expect(writeText).toHaveBeenCalledWith(
          expect.stringContaining("Bright Smile Dental Studio"),
        );
        expect(writeText).toHaveBeenCalledWith(expect.stringContaining("+15550001234"));
        expect(await screen.findByText("Copied")).toBeInTheDocument();
      });

      it("shows an honest error if the copy itself fails, not a silent no-op", async () => {
        const user = userEvent.setup();
        const writeText = vi.fn().mockRejectedValue(new Error("denied"));
        mockClipboard(writeText);
        renderWithProviders();

        await user.click(await screen.findByRole("button", { name: "Connect WhatsApp" }));
        await user.click(screen.getByRole("button", { name: "Continue" }));
        await user.type(screen.getByPlaceholderText("+1 555 000 1234"), "+15550001234");
        await user.click(screen.getByRole("button", { name: /copy request details/i }));

        expect(await screen.findByText("Couldn't copy automatically")).toBeInTheDocument();
        expect(screen.getByText(/select the text above and copy it manually/i)).toBeInTheDocument();
      });

      it("resets back to the intro step after closing and reopening", async () => {
        const user = userEvent.setup();
        renderWithProviders();

        await user.click(await screen.findByRole("button", { name: "Connect WhatsApp" }));
        await user.click(screen.getByRole("button", { name: "Continue" }));
        expect(
          screen.getByRole("heading", { name: "Your WhatsApp Business number" }),
        ).toBeInTheDocument();

        // The details step has Back/Copy, not Cancel — close via the dialog's
        // own Close control instead, same as a user pressing Escape or
        // clicking outside.
        await user.click(screen.getByRole("button", { name: "Close" }));
        expect(
          screen.queryByRole("heading", { name: "Your WhatsApp Business number" }),
        ).not.toBeInTheDocument();

        await user.click(await screen.findByRole("button", { name: "Connect WhatsApp" }));
        expect(screen.getByRole("heading", { name: "Connect WhatsApp" })).toBeInTheDocument();
        expect(
          screen.queryByRole("heading", { name: "Your WhatsApp Business number" }),
        ).not.toBeInTheDocument();
      });

      it("opens automatically when navigated here with ?whatsapp=connect", async () => {
        mockSearchParams.mockReturnValue(new URLSearchParams("whatsapp=connect"));
        renderWithProviders();

        expect(
          await screen.findByRole("heading", { name: "Connect WhatsApp" }),
        ).toBeInTheDocument();
      });
    });
  });

  describe("Appearance", () => {
    it("renders the real theme toggle", async () => {
      renderWithProviders();
      await screen.findByText("Appearance");
      expect(screen.getByRole("button", { name: /toggle theme/i })).toBeInTheDocument();
    });
  });

  describe("Security", () => {
    it("routes to the real sign-in provider's account management, not a fake control", async () => {
      const user = userEvent.setup();
      renderWithProviders();

      const button = await screen.findByRole("button", { name: "Manage account security" });
      await user.click(button);
      expect(openProfile).toHaveBeenCalledTimes(1);
    });
  });

  describe("Heading hierarchy", () => {
    it("groups settings under real section headings", async () => {
      renderWithProviders();
      await screen.findByText("Business profile");

      const h1s = screen.getAllByRole("heading", { level: 1 });
      expect(h1s).toHaveLength(1);
      expect(h1s[0]).toHaveTextContent("Settings");

      const h2s = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
      expect(h2s).toEqual(["Your business", "Your employee", "Connections", "Account"]);
    });
  });

  describe("AI Reply Mode", () => {
    it("selects the current mode once settings load", async () => {
      renderWithProviders();

      await waitFor(() => expect(screen.getByRole("radio", { name: /assisted/i })).toBeChecked());
      expect(screen.getByRole("radio", { name: /autonomous/i })).not.toBeChecked();
    });

    it("disables Save until the mode is changed", async () => {
      renderWithProviders();

      await waitFor(() => expect(screen.getByRole("radio", { name: /assisted/i })).toBeChecked());
      expect(within(aiReplyModeCard()).getByRole("button", { name: /save/i })).toBeDisabled();
    });

    it("mentions escalation is always available regardless of reply mode", async () => {
      renderWithProviders();
      expect(
        await screen.findByText(/escalate any conversation to yourself from Pending Replies/i),
      ).toBeInTheDocument();
    });

    it("saves the new mode, shows a success toast, and disables controls while saving", async () => {
      const user = userEvent.setup();
      let resolveUpdate: (value: { mode: "autonomous" }) => void;
      vi.mocked(api.updateSettings).mockImplementation(
        () =>
          new Promise((resolve) => {
            resolveUpdate = resolve;
          }),
      );

      renderWithProviders();

      await waitFor(() => expect(screen.getByRole("radio", { name: /assisted/i })).toBeChecked());

      await user.click(screen.getByRole("radio", { name: /autonomous/i }));
      const saveButton = within(aiReplyModeCard()).getByRole("button", { name: /save/i });
      expect(saveButton).not.toBeDisabled();

      await user.click(saveButton);

      await waitFor(() => expect(saveButton).toBeDisabled());
      expect(screen.getByRole("radio", { name: /assisted/i })).toBeDisabled();
      expect(screen.getByRole("radio", { name: /autonomous/i })).toBeDisabled();

      resolveUpdate!({ mode: "autonomous" });

      await waitFor(() => expect(screen.getByText("Settings saved")).toBeInTheDocument());
      expect(api.updateSettings).toHaveBeenCalledWith(expect.any(Function), {
        mode: "autonomous",
      });
    });

    it("shows a destructive toast when saving fails", async () => {
      const user = userEvent.setup();
      vi.mocked(api.updateSettings).mockRejectedValue(new Error("Network error"));

      renderWithProviders();

      await waitFor(() => expect(screen.getByRole("radio", { name: /assisted/i })).toBeChecked());
      await user.click(screen.getByRole("radio", { name: /autonomous/i }));
      await user.click(within(aiReplyModeCard()).getByRole("button", { name: /save/i }));

      await waitFor(() => expect(screen.getByText("Couldn't save settings")).toBeInTheDocument());
    });

    it("shows a retryable error state when AI Reply Mode fails to load", async () => {
      vi.mocked(api.getSettings).mockRejectedValue(new Error("Network error"));
      renderWithProviders();

      expect(
        await within(aiReplyModeCard()).findByText("Couldn't load AI Reply Mode"),
      ).toBeInTheDocument();
      expect(within(aiReplyModeCard()).queryByRole("radiogroup")).not.toBeInTheDocument();
    });
  });
});
