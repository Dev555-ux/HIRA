import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
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
  },
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
    expect(screen.queryByRole("button", { name: /continue with facebook/i })).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("shows Continue with Facebook once both the frontend and backend confirm Embedded Signup is ready", async () => {
    configState.enabled = true;
    vi.mocked(api.getEmbeddedSignupConfig).mockResolvedValue({ enabled: true });

    renderWithProviders();

    expect(await screen.findByRole("button", { name: /continue with facebook/i })).toBeInTheDocument();
  });
});
