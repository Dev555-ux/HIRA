import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import ConnectWhatsAppPage from "./page";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

const configState = vi.hoisted(() => ({ enabled: false }));
vi.mock("@/lib/config", () => ({
  get embeddedSignupEnabled() {
    return configState.enabled;
  },
}));

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: {
    getEmbeddedSignupConfig: vi.fn(),
    startEmbeddedSignup: vi.fn(),
    completeEmbeddedSignup: vi.fn(),
    getWhatsAppStatus: vi.fn(),
  },
}));

// The SDK half of the flow is mocked at the module boundary: these tests
// exercise the screens and the orchestration, and `facebook-sdk.ts` is
// tested on its own (message-origin checking in particular).
const sdk = vi.hoisted(() => ({
  loadFacebookSdk: vi.fn(),
  launchEmbeddedSignup: vi.fn(),
  listenForPopupEvents: vi.fn(),
}));
vi.mock("@/lib/facebook-sdk", () => sdk);

import { api } from "@/lib/api";

const mockAuth: AuthContextValue = {
  getToken: async () => "test-token",
  user: { name: "Dev User", email: "owner@acme.com", imageUrl: null },
  isLoaded: true,
  mocked: true,
  signOut: vi.fn(),
  openProfile: vi.fn(),
};

function renderWithProviders() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={mockAuth}>
        <ConnectWhatsAppPage />
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

/** The whole flow wired for success, so each test overrides only the step
 * it's about. */
function happyPath() {
  configState.enabled = true;
  vi.mocked(api.getEmbeddedSignupConfig).mockResolvedValue({ enabled: true });
  vi.mocked(api.getWhatsAppStatus).mockResolvedValue({
    connected: false,
    status: "not_connected",
    phone_number_id_masked: null,
    display_phone_number: null,
    connected_at: null,
    last_inbound_at: null,
  });
  vi.mocked(api.startEmbeddedSignup).mockResolvedValue({
    config_id: "config-abc",
    state: "signed-state",
  });
  vi.mocked(api.completeEmbeddedSignup).mockResolvedValue({
    success: true,
    display_phone_number: "+1 555 010 0000",
    error_code: null,
  });
  sdk.loadFacebookSdk.mockResolvedValue({});
  sdk.launchEmbeddedSignup.mockResolvedValue("auth-code");
  sdk.listenForPopupEvents.mockImplementation((onEvent: (e: unknown) => void) => {
    onEvent({ kind: "finished", wabaId: "WABA1", phoneNumberId: "PN1" });
    return () => {};
  });
}

describe("ConnectWhatsAppPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    configState.enabled = false;
  });

  it("redirects to the manual connect flow when the frontend flag is off", () => {
    renderWithProviders();

    expect(replace).toHaveBeenCalledWith("/settings?whatsapp=connect");
  });

  it("falls back to manual setup when the backend reports Embedded Signup isn't configured", async () => {
    configState.enabled = true;
    vi.mocked(api.getEmbeddedSignupConfig).mockResolvedValue({ enabled: false });

    renderWithProviders();

    expect(
      await screen.findByText(/Connect with your existing Meta credentials instead/i),
    ).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("connects end to end and offers a real test message", async () => {
    happyPath();
    renderWithProviders();

    await userEvent.click(await screen.findByRole("button", { name: /^connect whatsapp$/i }));

    expect(await screen.findByText(/you're connected/i)).toBeInTheDocument();
    expect(screen.getByText(/\+1 555 010 0000/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /send yourself a test message/i })).toHaveAttribute(
      "href",
      "https://wa.me/15550100000",
    );
  });

  it("passes the popup's reported ids to the backend as hints", async () => {
    happyPath();
    renderWithProviders();

    await userEvent.click(await screen.findByRole("button", { name: /^connect whatsapp$/i }));

    await waitFor(() =>
      expect(api.completeEmbeddedSignup).toHaveBeenCalledWith(expect.anything(), {
        code: "auth-code",
        state: "signed-state",
        waba_id: "WABA1",
        phone_number_id: "PN1",
      }),
    );
  });

  it("treats a closed popup as recoverable, not an error the owner caused", async () => {
    happyPath();
    sdk.launchEmbeddedSignup.mockResolvedValue(null);
    sdk.listenForPopupEvents.mockImplementation((onEvent: (e: unknown) => void) => {
      onEvent({ kind: "cancelled", step: "PHONE_NUMBER" });
      return () => {};
    });
    renderWithProviders();

    await userEvent.click(await screen.findByRole("button", { name: /^connect whatsapp$/i }));

    expect(await screen.findByText(/didn't finish/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
    expect(api.completeEmbeddedSignup).not.toHaveBeenCalled();
  });

  it("explains a declined permission distinctly from a closed window", async () => {
    happyPath();
    sdk.launchEmbeddedSignup.mockResolvedValue(null);
    sdk.listenForPopupEvents.mockImplementation((onEvent: (e: unknown) => void) => {
      onEvent({ kind: "error", message: "user denied" });
      return () => {};
    });
    renderWithProviders();

    await userEvent.click(await screen.findByRole("button", { name: /^connect whatsapp$/i }));

    expect(await screen.findByText(/missing a permission/i)).toBeInTheDocument();
  });

  it("offers no retry for a number connected to another account", async () => {
    happyPath();
    vi.mocked(api.completeEmbeddedSignup).mockResolvedValue({
      success: false,
      display_phone_number: null,
      error_code: "phone_number_in_use",
    });
    renderWithProviders();

    await userEvent.click(await screen.findByRole("button", { name: /^connect whatsapp$/i }));

    expect(await screen.findByText(/already connected/i)).toBeInTheDocument();
    // Retrying cannot fix this, so the screen must not invite a loop.
    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
  });

  it("surfaces an expired state as a fresh, retryable start", async () => {
    happyPath();
    vi.mocked(api.completeEmbeddedSignup).mockResolvedValue({
      success: false,
      display_phone_number: null,
      error_code: "state_invalid",
    });
    renderWithProviders();

    await userEvent.click(await screen.findByRole("button", { name: /^connect whatsapp$/i }));

    expect(await screen.findByText(/expired/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("blames neither the owner nor HIRA when Meta is down, and allows a retry", async () => {
    happyPath();
    vi.mocked(api.completeEmbeddedSignup).mockResolvedValue({
      success: false,
      display_phone_number: null,
      error_code: "meta_unavailable",
    });
    renderWithProviders();

    await userEvent.click(await screen.findByRole("button", { name: /^connect whatsapp$/i }));

    expect(await screen.findByText(/isn't responding right now/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("points at manual setup when the SDK itself can't load", async () => {
    happyPath();
    sdk.loadFacebookSdk.mockRejectedValue(new Error("blocked"));
    renderWithProviders();

    await userEvent.click(await screen.findByRole("button", { name: /^connect whatsapp$/i }));

    expect(await screen.findByText(/couldn't open the facebook window/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /existing meta credentials/i })).toBeInTheDocument();
    expect(api.startEmbeddedSignup).not.toHaveBeenCalled();
  });

  it("frames an already-connected business as reconnecting", async () => {
    happyPath();
    vi.mocked(api.getWhatsAppStatus).mockResolvedValue({
      connected: true,
      status: "connected",
      phone_number_id_masked: "••••0000",
      display_phone_number: "+1 555 010 0000",
      connected_at: "2026-09-01T00:00:00Z",
      last_inbound_at: null,
    });
    renderWithProviders();

    expect(await screen.findByRole("button", { name: /reconnect whatsapp/i })).toBeInTheDocument();
    expect(screen.getByText(/stay exactly as they are/i)).toBeInTheDocument();
  });

  it("never shows Meta jargon on any failure screen", async () => {
    happyPath();
    vi.mocked(api.completeEmbeddedSignup).mockResolvedValue({
      success: false,
      display_phone_number: null,
      error_code: "subscription_failed",
    });
    renderWithProviders();

    await userEvent.click(await screen.findByRole("button", { name: /^connect whatsapp$/i }));
    await screen.findByText(/one step didn't finish/i);

    // DEC-052 §3's language rule, enforced rather than trusted.
    const body = document.body.textContent ?? "";
    for (const word of ["webhook", "Graph API", "access token", "App Secret", "OAuth"]) {
      expect(body.toLowerCase()).not.toContain(word.toLowerCase());
    }
  });
});
