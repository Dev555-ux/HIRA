import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/toast";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import type { CustomerDetail, Lead } from "@/lib/types";
import LeadsPage from "./page";

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: {
    listLeads: vi.fn(),
    getCustomer: vi.fn(),
    getCustomerTimeline: vi.fn(),
    createCustomer: vi.fn(),
    updateCustomer: vi.fn(),
    deleteCustomer: vi.fn(),
    createLead: vi.fn(),
    updateLead: vi.fn(),
    deleteLead: vi.fn(),
  },
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

function lead(overrides: Partial<Lead> = {}): Lead {
  return {
    id: "lead-1",
    customer: { id: "cust-1", display_name: "Alice Smith", wa_phone: "+15551230000" },
    stage: "qualified",
    source: null,
    estimated_value: null,
    notes: null,
    next_follow_up_at: null,
    assigned_to: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

function customerDetail(overrides: Partial<CustomerDetail> = {}): CustomerDetail {
  return {
    id: "cust-1",
    display_name: "Alice Smith",
    wa_phone: "+15551230000",
    email: null,
    notes: null,
    created_at: new Date().toISOString(),
    conversation_count: 2,
    last_message_at: new Date().toISOString(),
    lead: null,
    ...overrides,
  };
}

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

describe("LeadsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getCustomerTimeline).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 20, offset: 0 },
    });
  });

  it("shows the empty state when there are no leads", async () => {
    vi.mocked(api.listLeads).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 20, offset: 0 },
    });
    renderWithProviders(<LeadsPage />);
    expect(await screen.findByText("No leads yet")).toBeInTheDocument();
  });

  it("shows an error state with retry when the list fails to load", async () => {
    vi.mocked(api.listLeads).mockRejectedValue(new Error("Network error"));
    renderWithProviders(<LeadsPage />);

    expect(await screen.findByText("Couldn't load leads")).toBeInTheDocument();
    expect(screen.getByText("Network error")).toBeInTheDocument();
  });

  it("renders a lead row with stage badge and estimated value", async () => {
    vi.mocked(api.listLeads).mockResolvedValue({
      data: [lead({ stage: "qualified", estimated_value: 1500 })],
      meta: { total: 1, limit: 20, offset: 0 },
    });

    renderWithProviders(<LeadsPage />);

    expect(await screen.findByText("Alice Smith")).toBeInTheDocument();
    // "Qualified" also appears as a stage filter chip, so there are two matches.
    expect(screen.getAllByText("Qualified").length).toBe(2);
    expect(screen.getByText("$1,500")).toBeInTheDocument();
  });

  it("debounces search input, then calls the API with the search term", async () => {
    vi.mocked(api.listLeads).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 20, offset: 0 },
    });
    const user = userEvent.setup();
    renderWithProviders(<LeadsPage />);
    await screen.findByText("No leads yet");

    await user.type(screen.getByPlaceholderText(/search leads/i), "alice");

    await waitFor(
      () =>
        expect(api.listLeads).toHaveBeenCalledWith(
          expect.any(Function),
          expect.objectContaining({ search: "alice" }),
        ),
      { timeout: 1000 },
    );
  });

  it("filters by stage using the filter chips", async () => {
    vi.mocked(api.listLeads).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 20, offset: 0 },
    });
    const user = userEvent.setup();
    renderWithProviders(<LeadsPage />);
    await screen.findByText("No leads yet");

    await user.click(screen.getByRole("button", { name: "Won" }));

    await waitFor(() =>
      expect(api.listLeads).toHaveBeenCalledWith(
        expect.any(Function),
        expect.objectContaining({ stage: "won" }),
      ),
    );
  });

  it("paginates using the Previous/Next controls", async () => {
    vi.mocked(api.listLeads).mockResolvedValue({
      data: [lead()],
      meta: { total: 45, limit: 20, offset: 0 },
    });
    const user = userEvent.setup();
    renderWithProviders(<LeadsPage />);
    await screen.findByText("Alice Smith");

    expect(screen.getByText("1–20 of 45")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() =>
      expect(api.listLeads).toHaveBeenCalledWith(
        expect.any(Function),
        expect.objectContaining({ offset: 20 }),
      ),
    );
  });

  it("opens the shared customer detail pane when a lead is selected", async () => {
    vi.mocked(api.listLeads).mockResolvedValue({
      data: [lead()],
      meta: { total: 1, limit: 20, offset: 0 },
    });
    vi.mocked(api.getCustomer).mockResolvedValue(
      customerDetail({
        lead: {
          id: "lead-1",
          stage: "qualified",
          source: null,
          estimated_value: null,
          notes: null,
          next_follow_up_at: null,
          assigned_to: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      }),
    );
    const user = userEvent.setup();

    renderWithProviders(<LeadsPage />);
    await user.click(await screen.findByText("Alice Smith"));

    expect(await screen.findByText("+15551230000 · 2 conversations")).toBeInTheDocument();
    expect(api.getCustomer).toHaveBeenCalledWith(expect.any(Function), "cust-1");
  });
});
