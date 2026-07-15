import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import { ToastProvider } from "@/components/ui/toast";
import type { Business } from "@/lib/types";
import { OnboardingChecklist } from "./onboarding-checklist";

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: { listKbEntries: vi.fn() },
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

function business(overrides: Partial<Business> = {}): Business {
  return {
    id: "biz-1",
    name: "Acme Clinic",
    industry: null,
    contact_email: null,
    country: null,
    timezone: "UTC",
    onboarding_status: "created",
    whatsapp_connection_status: "not_connected",
    ...overrides,
  };
}

function renderChecklist(biz: Business) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={mockAuth}>
        <ToastProvider>
          <OnboardingChecklist business={biz} />
        </ToastProvider>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

describe("OnboardingChecklist", () => {
  beforeEach(() => vi.clearAllMocks());

  it("never shows a 'Coming soon' placeholder", async () => {
    vi.mocked(api.listKbEntries).mockResolvedValue([]);
    renderChecklist(business());

    await waitFor(() => expect(screen.getByText("0 of 4 done")).toBeInTheDocument());
    expect(screen.queryByText("Coming soon")).not.toBeInTheDocument();
  });

  it("shows Connect and a disabled Complete-setup-first state for a brand-new business", async () => {
    vi.mocked(api.listKbEntries).mockResolvedValue([]);
    renderChecklist(business());

    await waitFor(() => expect(screen.getByText("0 of 4 done")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Connect" })).toHaveAttribute("href", "/settings");
    expect(screen.getByRole("button", { name: "Complete setup first" })).toBeDisabled();
  });

  it("marks Teach HIRA done once at least one KB entry exists", async () => {
    vi.mocked(api.listKbEntries).mockResolvedValue([
      { id: "1", title: "Hours", content: "9-5", created_at: "", updated_at: "" },
    ]);
    renderChecklist(business());

    await waitFor(() => expect(screen.getByText("1 of 4 done")).toBeInTheDocument());
    expect(screen.getByText("Done")).toBeInTheDocument();
  });

  it("shows Retry when WhatsApp connection is pending verification", async () => {
    vi.mocked(api.listKbEntries).mockResolvedValue([]);
    renderChecklist(business({ whatsapp_connection_status: "pending_verification" }));

    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Retry" })).toHaveAttribute("href", "/settings"),
    );
  });

  it("shows Enable AI once prerequisites are met, and it's a real toast, not a fake success", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listKbEntries).mockResolvedValue([
      { id: "1", title: "Hours", content: "9-5", created_at: "", updated_at: "" },
    ]);
    renderChecklist(business({ whatsapp_connection_status: "connected" }));

    const enableButton = await screen.findByRole("button", { name: "Enable AI" });
    await user.click(enableButton);

    expect(await screen.findByText("We'll take it from here")).toBeInTheDocument();
  });

  it("marks WhatsApp Connection Connected and Go Live Live from real business fields", async () => {
    vi.mocked(api.listKbEntries).mockResolvedValue([
      { id: "1", title: "Hours", content: "9-5", created_at: "", updated_at: "" },
    ]);
    renderChecklist(
      business({ whatsapp_connection_status: "connected", onboarding_status: "live" }),
    );

    await waitFor(() => expect(screen.getByText("3 of 4 done")).toBeInTheDocument());
    expect(screen.getByText("Connected")).toBeInTheDocument();
    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.queryByText("Coming soon")).not.toBeInTheDocument();
  });

  it("fades completed-step badges in rather than popping them in instantly", async () => {
    vi.mocked(api.listKbEntries).mockResolvedValue([
      { id: "1", title: "Hours", content: "9-5", created_at: "", updated_at: "" },
    ]);
    renderChecklist(
      business({ whatsapp_connection_status: "connected", onboarding_status: "live" }),
    );

    await waitFor(() => expect(screen.getByText("3 of 4 done")).toBeInTheDocument());
    expect(screen.getByText("Done")).toHaveClass("animate-fade-in");
    expect(screen.getByText("Connected")).toHaveClass("animate-fade-in");
    expect(screen.getByText("Live")).toHaveClass("animate-fade-in");
  });

  it("links Teach HIRA and Test AI to the real, already-live pages", async () => {
    vi.mocked(api.listKbEntries).mockResolvedValue([]);
    renderChecklist(business());

    const links = await screen.findAllByRole("link", { name: /get started/i });
    const hrefs = links.map((link) => link.getAttribute("href"));
    expect(hrefs).toEqual(expect.arrayContaining(["/knowledge-base", "/playground"]));
  });
});
