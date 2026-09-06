import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import { ToastProvider } from "@/components/ui/toast";
import type { OnboardingStatus } from "@/lib/types";
import SettingsPage from "./page";

function aiReplyModeCard() {
  // M13: this card carries the AI-identity spine (aiSurfaceClassName), which
  // uses rounded-lg rather than the plain Card's rounded-xl — the only card
  // on this page with that corner radius.
  return screen.getByText("How your employee responds").closest<HTMLElement>(".rounded-lg")!;
}

function aiEmployeeCard() {
  return screen.getByText("AI Employee").closest<HTMLElement>(".rounded-2xl")!;
}

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
  api: {
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
    getOnboardingStatus: vi.fn(),
    listKbEntries: vi.fn(),
    getCalendarStatus: vi.fn(),
    getWhatsAppStatus: vi.fn(),
    connectWhatsApp: vi.fn(),
    disconnectWhatsApp: vi.fn(),
    getWhatsAppWebhookConfig: vi.fn(),
  },
}));

const mockSearchParams = vi.fn(() => new URLSearchParams());
vi.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams(),
}));

import { ApiError, api } from "@/lib/api";

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
    vi.mocked(api.getWhatsAppStatus).mockResolvedValue({
      connected: false,
      status: "not_connected",
      phone_number_id_masked: null,
      display_phone_number: null,
      connected_at: null,
      last_inbound_at: null,
    });
    vi.mocked(api.getWhatsAppWebhookConfig).mockResolvedValue({
      callback_url: "https://hira-production.up.railway.app/webhooks/whatsapp",
      verify_token: "test-verify-token",
    });
    if (!navigator.clipboard) {
      Object.defineProperty(navigator, "clipboard", { value: {}, configurable: true });
    }
    Object.defineProperty(navigator.clipboard, "writeText", {
      value: vi.fn().mockResolvedValue(undefined),
      configurable: true,
    });
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
        ".rounded-2xl",
      )!;
      expect(within(profileCard).queryByText("America/Chicago")).not.toBeInTheDocument();
    });
  });

  describe("Knowledge", () => {
    it("shows the real knowledge base count and links to the real page", async () => {
      vi.mocked(api.listKbEntries).mockResolvedValue([
        { id: "1", title: "Hours", content: "9-5", status: "published", import_batch_id: null, created_at: "", updated_at: "" },
        { id: "2", title: "Pricing", content: "$50", status: "published", import_batch_id: null, created_at: "", updated_at: "" },
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

  describe("HIRA Calendar", () => {
    it("shows Google Sync status and timezone, linking to the real Calendar page", async () => {
      vi.mocked(api.getCalendarStatus).mockResolvedValue({
        connected: true,
        calendar_id: "primary",
      });
      renderWithProviders();

      expect(await screen.findByText("Google Sync Enabled")).toBeInTheDocument();
      expect(screen.getByText("America/Chicago")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Manage calendar" })).toHaveAttribute(
        "href",
        "/calendar",
      );
    });

    it("shows Active, never a warning, when Google Calendar isn't connected yet", async () => {
      renderWithProviders();
      expect(await screen.findByText("Active")).toBeInTheDocument();
      expect(
        screen.getByText(/HIRA Calendar manages your appointments automatically/i),
      ).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Manage calendar" })).toHaveAttribute(
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
      expect(
        screen.getByText(/customers keep messaging the number they already know/i),
      ).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Connect WhatsApp" })).toBeInTheDocument();
    });

    it("shows the reward, masked number, and real connection health once connected, not a dead badge", async () => {
      vi.mocked(api.getWhatsAppStatus).mockResolvedValue({
        connected: true,
        status: "connected",
        phone_number_id_masked: "••••7890",
        display_phone_number: null,
        connected_at: "2026-07-22T00:00:00Z",
        last_inbound_at: null,
      });
      renderWithProviders();

      expect(
        await screen.findByText(/customers can message your business through WhatsApp/i),
      ).toBeInTheDocument();
      expect(screen.getByText("••••7890")).toBeInTheDocument();
      // Demo Chat is no longer presented as proof of WhatsApp connectivity
      // (Sprint 71, Task B) — no more "Send a test message" link to /demo.
      expect(screen.queryByRole("link", { name: "Send a test message" })).not.toBeInTheDocument();
      expect(screen.getByText("No messages received yet")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Check connection" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /disconnect/i })).toBeInTheDocument();
    });

    it("prefers the real dialable number over the masked technical ID once Meta has told us it (Sprint 72)", async () => {
      vi.mocked(api.getWhatsAppStatus).mockResolvedValue({
        connected: true,
        status: "connected",
        phone_number_id_masked: "••••7890",
        display_phone_number: "+1 555 123 0000",
        connected_at: "2026-07-22T00:00:00Z",
        last_inbound_at: null,
      });
      renderWithProviders();

      expect(await screen.findByText("+1 555 123 0000")).toBeInTheDocument();
      expect(screen.queryByText("••••7890")).not.toBeInTheDocument();
    });

    it("shows the real last-inbound timestamp once a real message has arrived", async () => {
      vi.mocked(api.getWhatsAppStatus).mockResolvedValue({
        connected: true,
        status: "connected",
        phone_number_id_masked: "••••7890",
        display_phone_number: null,
        connected_at: "2026-07-22T00:00:00Z",
        last_inbound_at: new Date().toISOString(),
      });
      renderWithProviders();

      expect(await screen.findByText(/last message/i)).toBeInTheDocument();
      expect(screen.queryByText("No messages received yet")).not.toBeInTheDocument();
    });

    it("shows business-language status, not the raw backend enum", async () => {
      vi.mocked(api.getWhatsAppStatus).mockResolvedValue({
        connected: false,
        status: "pending_verification",
        phone_number_id_masked: null,
        display_phone_number: null,
        connected_at: null,
        last_inbound_at: null,
      });
      renderWithProviders();

      expect(await screen.findByText("Needs attention")).toBeInTheDocument();
      expect(screen.queryByText("pending_verification")).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Continue setup" })).toBeInTheDocument();
    });

    describe("disconnect", () => {
      it("asks for confirmation before disconnecting", async () => {
        const user = userEvent.setup();
        vi.mocked(api.getWhatsAppStatus).mockResolvedValue({
          connected: true,
          status: "connected",
          phone_number_id_masked: "••••7890",
          display_phone_number: null,
          connected_at: "2026-07-22T00:00:00Z",
          last_inbound_at: null,
        });
        renderWithProviders();

        await user.click(await screen.findByRole("button", { name: /disconnect/i }));
        expect(screen.getByRole("heading", { name: "Disconnect WhatsApp?" })).toBeInTheDocument();
        expect(api.disconnectWhatsApp).not.toHaveBeenCalled();

        await user.click(screen.getByRole("button", { name: "Disconnect" }));
        await waitFor(() => expect(api.disconnectWhatsApp).toHaveBeenCalledTimes(1));
      });
    });

    describe("connection wizard", () => {
      it("offers per-field setup help, collapsed by default, expandable on demand (Sprint 72; DEC-053 split this per field)", async () => {
        const user = userEvent.setup();
        renderWithProviders();

        await user.click(await screen.findByRole("button", { name: "Connect WhatsApp" }));
        const dialog = screen.getByRole("dialog");
        await user.click(within(dialog).getByRole("button", { name: "Connect WhatsApp" })); // entry -> phone

        const appToggle = screen.getByRole("button", { name: /don't have a meta app yet/i });
        expect(appToggle).toHaveAttribute("aria-expanded", "false");
        expect(screen.queryByText("Create a Meta App")).not.toBeInTheDocument();

        await user.click(appToggle);

        expect(appToggle).toHaveAttribute("aria-expanded", "true");
        expect(screen.getByText("Create a Meta App")).toBeInTheDocument();
        expect(screen.getAllByRole("link", { name: /meta's guide/i }).length).toBeGreaterThan(0);

        // The System User / access-token help lives on the token step instead
        // (DEC-053: relocated to where each is first needed, not upfront).
        await user.type(screen.getByLabelText("Your WhatsApp Number", { selector: "input" }), "9876543210");
        await user.click(screen.getByRole("button", { name: "Continue" }));
        await user.type(screen.getByLabelText("Business Account", { selector: "input" }), "waba-123");
        await user.click(screen.getByRole("button", { name: "Continue" }));

        const tokenToggle = screen.getByRole("button", { name: /don't have an access token yet/i });
        expect(tokenToggle).toHaveAttribute("aria-expanded", "false");
        expect(screen.queryByText("Create a System User")).not.toBeInTheDocument();

        await user.click(tokenToggle);

        expect(tokenToggle).toHaveAttribute("aria-expanded", "true");
        expect(screen.getByText("Create a System User")).toBeInTheDocument();
        expect(screen.getByText("Generate a permanent access token")).toBeInTheDocument();
      });

      it("walks from the entry screen through the field-by-field form, submits real credentials, and lands on webhook setup (DEC-053/054 replaced the combined form)", async () => {
        const user = userEvent.setup();
        vi.mocked(api.connectWhatsApp).mockResolvedValue({
          connected: true,
          status: "connected",
          phone_number_id_masked: "••••7890",
          display_phone_number: null,
          connected_at: "2026-07-22T00:00:00Z",
          last_inbound_at: null,
        });
        renderWithProviders();

        await user.click(await screen.findByRole("button", { name: "Connect WhatsApp" }));
        const dialog = screen.getByRole("dialog");
        expect(within(dialog).getByRole("heading", { name: "Connect WhatsApp" })).toBeInTheDocument();
        expect(
          within(dialog).getByText(/your customers will continue using the same number/i),
        ).toBeInTheDocument();

        await user.click(within(dialog).getByRole("button", { name: "Connect WhatsApp" })); // entry -> phone
        expect(screen.getByRole("heading", { name: "Your WhatsApp Number" })).toBeInTheDocument();

        await user.type(screen.getByLabelText("Your WhatsApp Number", { selector: "input" }), "9876543210");
        await user.click(screen.getByRole("button", { name: "Continue" }));

        expect(screen.getByRole("heading", { name: "Business Account" })).toBeInTheDocument();
        await user.type(screen.getByLabelText("Business Account", { selector: "input" }), "waba-123");
        await user.click(screen.getByRole("button", { name: "Continue" }));

        expect(screen.getByRole("heading", { name: "Access Key" })).toBeInTheDocument();
        await user.type(screen.getByLabelText("Access Key", { selector: "input" }), "real-access-token");
        await user.click(screen.getByRole("button", { name: "Continue" }));

        expect(screen.getByRole("heading", { name: "App Secret" })).toBeInTheDocument();
        await user.type(screen.getByLabelText("App Secret", { selector: "input" }), "real-app-secret");
        await user.click(screen.getByRole("button", { name: "Connect" }));

        await waitFor(() =>
          expect(api.connectWhatsApp).toHaveBeenCalledWith(expect.any(Function), {
            phone_number_id: "9876543210",
            whatsapp_business_account_id: "waba-123",
            access_token: "real-access-token",
            app_secret: "real-app-secret",
          }),
        );

        // Task A: credentials verifying isn't the end — the wizard now shows
        // the webhook values instead of a premature "connected" toast.
        expect(await screen.findByRole("heading", { name: "Set up your webhook" })).toBeInTheDocument();
        expect(screen.queryByText("WhatsApp connected")).not.toBeInTheDocument();
        expect(
          screen.getByDisplayValue("https://hira-production.up.railway.app/webhooks/whatsapp"),
        ).toBeInTheDocument();
        expect(screen.getByDisplayValue("test-verify-token")).toBeInTheDocument();
        expect(screen.getByText(/subscribe to the "messages" field/i)).toBeInTheDocument();

        await user.click(screen.getByRole("button", { name: "Copy Callback URL" }));
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
          "https://hira-production.up.railway.app/webhooks/whatsapp",
        );
        expect(await screen.findByText("Copied to clipboard")).toBeInTheDocument();

        // Task B: advancing moves to the real verification step, not a close.
        await user.click(screen.getByRole("button", { name: "Next: Verify connection" }));
        expect(await screen.findByRole("heading", { name: "Verify your connection" })).toBeInTheDocument();
        expect(screen.getByText(/waiting for your first whatsapp message/i)).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "I'll do this later" })).toBeInTheDocument();
      });

      it("shows a real success state, not a simulated one, once an inbound message is detected", async () => {
        // Entered via "Check connection" on an already-connected business —
        // the wizard's verify step must never infer success from
        // `connected`/stored credentials alone, only from last_inbound_at.
        const user = userEvent.setup();
        vi.mocked(api.getWhatsAppStatus).mockResolvedValue({
          connected: true,
          status: "connected",
          phone_number_id_masked: "••••7890",
          display_phone_number: null,
          connected_at: "2026-07-22T00:00:00Z",
          last_inbound_at: "2026-07-25T12:00:00Z",
        });
        renderWithProviders();

        await user.click(await screen.findByRole("button", { name: "Check connection" }));

        expect(await screen.findByRole("heading", { name: "Verify your connection" })).toBeInTheDocument();
        expect(screen.getByText("✅ WhatsApp Connected")).toBeInTheDocument();
        expect(screen.getByText(/last message received/i)).toBeInTheDocument();
        expect(screen.getByText("Webhook: Healthy")).toBeInTheDocument();
        expect(screen.queryByText(/waiting for your first whatsapp message/i)).not.toBeInTheDocument();
        expect(await screen.findByText("WhatsApp connected")).toBeInTheDocument(); // success toast

        await user.click(screen.getByRole("button", { name: "Done" }));
        expect(screen.queryByRole("heading", { name: "Verify your connection" })).not.toBeInTheDocument();
      });

      it("tells the owner the real number to text once Meta has reported it (Sprint 72)", async () => {
        const user = userEvent.setup();
        vi.mocked(api.getWhatsAppStatus).mockResolvedValue({
          connected: true,
          status: "connected",
          phone_number_id_masked: "••••7890",
          display_phone_number: "+1 555 123 0000",
          connected_at: "2026-07-22T00:00:00Z",
          last_inbound_at: null,
        });
        renderWithProviders();

        await user.click(await screen.findByRole("button", { name: "Check connection" }));

        const dialog = (await screen.findByRole("heading", { name: "Verify your connection" }))
          .closest<HTMLElement>('[role="dialog"]')!;
        expect(within(dialog).getByText(/send a whatsapp message from your phone to/i)).toBeInTheDocument();
        expect(within(dialog).getByText("+1 555 123 0000")).toBeInTheDocument();
        expect(within(dialog).queryByText(/your connected business number/i)).not.toBeInTheDocument();
      });

      it("falls back to generic wording when the real number isn't known yet", async () => {
        const user = userEvent.setup();
        vi.mocked(api.getWhatsAppStatus).mockResolvedValue({
          connected: true,
          status: "connected",
          phone_number_id_masked: "••••7890",
          display_phone_number: null,
          connected_at: "2026-07-22T00:00:00Z",
          last_inbound_at: null,
        });
        renderWithProviders();

        await user.click(await screen.findByRole("button", { name: "Check connection" }));

        expect(await screen.findByText(/your connected business number/i)).toBeInTheDocument();
      });

      it("shows a retryable error instead of a stuck loading state when webhook config fails to load", async () => {
        // Found during Sprint 71 release verification: without an isError
        // branch, a failed fetch left two skeletons showing forever.
        const user = userEvent.setup();
        vi.mocked(api.connectWhatsApp).mockResolvedValue({
          connected: true,
          status: "connected",
          phone_number_id_masked: "••••7890",
          display_phone_number: null,
          connected_at: "2026-07-22T00:00:00Z",
          last_inbound_at: null,
        });
        vi.mocked(api.getWhatsAppWebhookConfig).mockRejectedValue(new Error("Network error"));
        renderWithProviders();

        await user.click(await screen.findByRole("button", { name: "Connect WhatsApp" }));
        const dialog = screen.getByRole("dialog");
        await user.click(within(dialog).getByRole("button", { name: "Connect WhatsApp" })); // entry -> phone
        await user.type(screen.getByLabelText("Your WhatsApp Number", { selector: "input" }), "9876543210");
        await user.click(screen.getByRole("button", { name: "Continue" }));
        await user.type(screen.getByLabelText("Business Account", { selector: "input" }), "waba-123");
        await user.click(screen.getByRole("button", { name: "Continue" }));
        await user.type(screen.getByLabelText("Access Key", { selector: "input" }), "real-access-token");
        await user.click(screen.getByRole("button", { name: "Continue" }));
        await user.type(screen.getByLabelText("App Secret", { selector: "input" }), "real-app-secret");
        await user.click(screen.getByRole("button", { name: "Connect" }));

        expect(await screen.findByText("Couldn't load your webhook details")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Next: Verify connection" })).not.toBeInTheDocument();

        vi.mocked(api.getWhatsAppWebhookConfig).mockResolvedValue({
          callback_url: "https://hira-production.up.railway.app/webhooks/whatsapp",
          verify_token: "test-verify-token",
        });
        await user.click(screen.getByRole("button", { name: "Retry" }));

        expect(await screen.findByRole("heading", { name: "Set up your webhook" })).toBeInTheDocument();
        expect(screen.getByDisplayValue("test-verify-token")).toBeInTheDocument();
      });

      it("shows the specific rejection reason from the backend, without closing the form", async () => {
        const user = userEvent.setup();
        vi.mocked(api.connectWhatsApp).mockRejectedValue(
          new ApiError(422, "Meta rejected the access token — check you copied it."),
        );
        renderWithProviders();

        await user.click(await screen.findByRole("button", { name: "Connect WhatsApp" }));
        const dialog = screen.getByRole("dialog");
        await user.click(within(dialog).getByRole("button", { name: "Connect WhatsApp" })); // entry -> phone
        await user.type(screen.getByLabelText("Your WhatsApp Number", { selector: "input" }), "9876543210");
        await user.click(screen.getByRole("button", { name: "Continue" }));
        await user.type(screen.getByLabelText("Business Account", { selector: "input" }), "waba-123");
        await user.click(screen.getByRole("button", { name: "Continue" }));
        await user.type(screen.getByLabelText("Access Key", { selector: "input" }), "bad-token");
        await user.click(screen.getByRole("button", { name: "Continue" }));
        await user.type(screen.getByLabelText("App Secret", { selector: "input" }), "real-app-secret");
        await user.click(screen.getByRole("button", { name: "Connect" }));

        expect(
          await screen.findByText("Meta rejected the access token — check you copied it."),
        ).toBeInTheDocument();
        // Still open on the same field — the owner can fix and retry, not start over.
        expect(screen.getByRole("heading", { name: "App Secret" })).toBeInTheDocument();
      });

      it("resets back to the entry step after closing and reopening", async () => {
        const user = userEvent.setup();
        renderWithProviders();

        await user.click(await screen.findByRole("button", { name: "Connect WhatsApp" }));
        let dialog = screen.getByRole("dialog");
        await user.click(within(dialog).getByRole("button", { name: "Connect WhatsApp" })); // entry -> phone
        expect(screen.getByRole("heading", { name: "Your WhatsApp Number" })).toBeInTheDocument();

        await user.click(screen.getByRole("button", { name: "Close" }));
        expect(screen.queryByRole("heading", { name: "Your WhatsApp Number" })).not.toBeInTheDocument();

        await user.click(await screen.findByRole("button", { name: "Connect WhatsApp" }));
        dialog = screen.getByRole("dialog");
        expect(within(dialog).getByRole("heading", { name: "Connect WhatsApp" })).toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Your WhatsApp Number" })).not.toBeInTheDocument();
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

  describe("AI Employee", () => {
    it("shows status, knowledge learned, and reply mode in business language, never model/provider names", async () => {
      vi.mocked(api.listKbEntries).mockResolvedValue([
        { id: "1", title: "Hours", content: "9-5", status: "published", import_batch_id: null, created_at: "", updated_at: "" },
        { id: "2", title: "Pricing", content: "$50", status: "published", import_batch_id: null, created_at: "", updated_at: "" },
      ]);
      renderWithProviders();

      await screen.findByText("AI Employee");
      const card = aiEmployeeCard();
      expect(await within(card).findByText("Setting up")).toBeInTheDocument(); // onboarding_status: "created"
      expect(await within(card).findByText("2 facts")).toBeInTheDocument();
      expect(await within(card).findByText("Assisted")).toBeInTheDocument();

      expect(
        screen.queryByText(/groq|claude|llama|embedding|bge|local_bge|ai provider/i),
      ).not.toBeInTheDocument();
    });

    it("shows Live once the business has gone live", async () => {
      vi.mocked(api.getOnboardingStatus).mockResolvedValue({
        has_business: true,
        business: { ...onboardingStatus.business!, onboarding_status: "live" },
      });
      renderWithProviders();

      await screen.findByText("AI Employee");
      const card = aiEmployeeCard();
      expect(await within(card).findByText("Live")).toBeInTheDocument();
      expect(within(card).queryByText("Setting up")).not.toBeInTheDocument();
    });

    it("shows Autonomous once that's the saved reply mode", async () => {
      vi.mocked(api.getSettings).mockResolvedValue({ mode: "autonomous" });
      renderWithProviders();

      await screen.findByText("AI Employee");
      expect(await within(aiEmployeeCard()).findByText("Autonomous")).toBeInTheDocument();
    });
  });

  describe("No implementation details leak anywhere on the page", () => {
    it("never shows the old 'Systems' card or any internal model/provider name", async () => {
      vi.mocked(api.listKbEntries).mockResolvedValue([
        { id: "1", title: "Hours", content: "9-5", status: "published", import_batch_id: null, created_at: "", updated_at: "" },
      ]);
      vi.mocked(api.getCalendarStatus).mockResolvedValue({
        connected: true,
        calendar_id: "primary",
      });
      renderWithProviders();

      await screen.findByText("AI Employee");

      expect(screen.queryByText("Systems")).not.toBeInTheDocument();
      expect(screen.queryByText("Integrations")).not.toBeInTheDocument();
      expect(
        screen.queryByText(
          /groq|llama|claude|embedding|bge|local_bge|mock \(dev\)|on-device|phone number id|access token/i,
        ),
      ).not.toBeInTheDocument();
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
