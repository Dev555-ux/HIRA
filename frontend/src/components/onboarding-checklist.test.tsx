import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
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
        <OnboardingChecklist business={biz} />
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

describe("OnboardingChecklist", () => {
  beforeEach(() => vi.clearAllMocks());

  it("computes 0 of 4 done for a brand-new business with no KB entries", async () => {
    vi.mocked(api.listKbEntries).mockResolvedValue([]);
    renderChecklist(business());

    await waitFor(() => expect(screen.getByText("0 of 4 done")).toBeInTheDocument());
    // WhatsApp Connection and Go Live have no self-serve path yet.
    expect(screen.getAllByText("Coming soon")).toHaveLength(2);
  });

  it("marks Knowledge Import done once at least one KB entry exists", async () => {
    vi.mocked(api.listKbEntries).mockResolvedValue([
      { id: "1", title: "Hours", content: "9-5", created_at: "", updated_at: "" },
    ]);
    renderChecklist(business());

    await waitFor(() => expect(screen.getByText("1 of 4 done")).toBeInTheDocument());
    expect(screen.getByText("Done")).toBeInTheDocument();
  });

  it("marks WhatsApp Connection and Go Live done from real business fields", async () => {
    vi.mocked(api.listKbEntries).mockResolvedValue([]);
    renderChecklist(
      business({ whatsapp_connection_status: "connected", onboarding_status: "live" }),
    );

    await waitFor(() => expect(screen.getByText("2 of 4 done")).toBeInTheDocument());
    expect(screen.queryByText("Coming soon")).not.toBeInTheDocument();
  });

  it("links Knowledge Import and Test AI to the real, already-live pages", async () => {
    vi.mocked(api.listKbEntries).mockResolvedValue([]);
    renderChecklist(business());

    const links = await screen.findAllByRole("link", { name: /get started/i });
    const hrefs = links.map((link) => link.getAttribute("href"));
    expect(hrefs).toEqual(expect.arrayContaining(["/knowledge-base", "/playground"]));
  });
});
