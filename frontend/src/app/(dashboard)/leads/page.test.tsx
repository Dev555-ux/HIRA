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
    customer: { id: "cust-1", display_name: "Alice Smith", company: null, wa_phone: "+15551230000", email: null },
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
    company: null,
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

  // --- New Lead dialog (Sprint 38) ------------------------------------------

  it("opens the New Lead dialog from the header button", async () => {
    vi.mocked(api.listLeads).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 20, offset: 0 },
    });
    const user = userEvent.setup();

    renderWithProviders(<LeadsPage />);
    await screen.findByText("No leads yet");
    await user.click(screen.getAllByRole("button", { name: /new lead/i })[0]);

    expect(await screen.findByRole("heading", { name: "New lead" })).toBeInTheDocument();
  });

  it("offers New Lead from the empty state", async () => {
    vi.mocked(api.listLeads).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 20, offset: 0 },
    });
    const user = userEvent.setup();

    renderWithProviders(<LeadsPage />);
    await screen.findByText("No leads yet");

    const buttons = screen.getAllByRole("button", { name: /new lead/i });
    expect(buttons.length).toBeGreaterThan(1); // header action + empty-state CTA
    await user.click(buttons[buttons.length - 1]);

    expect(await screen.findByRole("heading", { name: "New lead" })).toBeInTheDocument();
  });

  it("rejects a blank full name without calling the API", async () => {
    vi.mocked(api.listLeads).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 20, offset: 0 },
    });
    const user = userEvent.setup();

    renderWithProviders(<LeadsPage />);
    await screen.findByText("No leads yet");
    await user.click(screen.getAllByRole("button", { name: /new lead/i })[0]);
    await screen.findByRole("heading", { name: "New lead" });

    await user.click(screen.getByRole("button", { name: "Create lead" }));

    expect(await screen.findByText("Full name is required")).toBeInTheDocument();
    expect(api.createLead).not.toHaveBeenCalled();
  });

  it("rejects an invalid email without calling the API", async () => {
    vi.mocked(api.listLeads).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 20, offset: 0 },
    });
    const user = userEvent.setup();

    renderWithProviders(<LeadsPage />);
    await screen.findByText("No leads yet");
    await user.click(screen.getAllByRole("button", { name: /new lead/i })[0]);
    await user.type(screen.getByLabelText("Full name"), "Jordan Lee");
    await user.type(screen.getByLabelText("Email"), "not-an-email");
    await user.click(screen.getByRole("button", { name: "Create lead" }));

    expect(await screen.findByText("Enter a valid email address")).toBeInTheDocument();
    expect(api.createLead).not.toHaveBeenCalled();
  });

  it("creates a lead, shows a success toast, refreshes the list, and selects the new lead's customer", async () => {
    vi.mocked(api.listLeads).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 20, offset: 0 },
    });
    const newLead = lead({
      id: "lead-new",
      customer: {
        id: "cust-new",
        display_name: "Jordan Lee",
        company: "Acme Co",
        wa_phone: "+15559876543",
        email: "jordan@example.com",
      },
      stage: "contacted",
      source: "referral",
      estimated_value: 1200,
    });
    vi.mocked(api.createLead).mockResolvedValue(newLead);
    vi.mocked(api.getCustomer).mockResolvedValue(
      customerDetail({
        id: "cust-new",
        display_name: "Jordan Lee",
        company: "Acme Co",
        wa_phone: "+15559876543",
        email: "jordan@example.com",
        conversation_count: 0,
        last_message_at: null,
      }),
    );
    const user = userEvent.setup();

    renderWithProviders(<LeadsPage />);
    await screen.findByText("No leads yet");
    await user.click(screen.getAllByRole("button", { name: /new lead/i })[0]);

    await user.type(screen.getByLabelText("Full name"), "Jordan Lee");
    await user.type(screen.getByLabelText("Company"), "Acme Co");
    await user.type(screen.getByLabelText("Email"), "jordan@example.com");
    await user.type(screen.getByLabelText("Phone"), "+15559876543");
    await user.selectOptions(screen.getByLabelText("Stage"), "contacted");
    await user.type(screen.getByLabelText("Source"), "referral");
    await user.type(screen.getByLabelText("Estimated value"), "1200");
    await user.click(screen.getByRole("button", { name: "Create lead" }));

    await waitFor(() =>
      expect(api.createLead).toHaveBeenCalledWith(expect.any(Function), {
        display_name: "Jordan Lee",
        company: "Acme Co",
        email: "jordan@example.com",
        wa_phone: "+15559876543",
        stage: "contacted",
        source: "referral",
        estimated_value: 1200,
        next_follow_up_at: null,
        notes: null,
      }),
    );
    expect(await screen.findByText("Lead created")).toBeInTheDocument();

    // Dialog closes on success.
    expect(screen.queryByRole("heading", { name: "New lead" })).not.toBeInTheDocument();

    // List refreshes automatically (query invalidation) — listLeads called again.
    await waitFor(() => expect(api.listLeads).toHaveBeenCalledTimes(2));

    // The new lead's customer is auto-selected in the detail pane.
    expect(
      await screen.findByText("Acme Co · +15559876543 · jordan@example.com · 0 conversations"),
    ).toBeInTheDocument();
    expect(api.getCustomer).toHaveBeenCalledWith(expect.any(Function), "cust-new");
  });

  it("shows an inline error and keeps the dialog open when creation fails", async () => {
    vi.mocked(api.listLeads).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 20, offset: 0 },
    });
    vi.mocked(api.createLead).mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();

    renderWithProviders(<LeadsPage />);
    await screen.findByText("No leads yet");
    await user.click(screen.getAllByRole("button", { name: /new lead/i })[0]);
    await user.type(screen.getByLabelText("Full name"), "Jordan Lee");
    await user.click(screen.getByRole("button", { name: "Create lead" }));

    // Non-ApiError rejections fall back to a generic message (matching
    // CustomerFormDialog/KbEntryForm's existing inline-error convention).
    expect(
      await screen.findByText("Something went wrong — please try again."),
    ).toBeInTheDocument();
    // Dialog stays open so the user doesn't lose their input, and the toast
    // ("Lead created") that only fires on success never appears.
    expect(screen.getByRole("heading", { name: "New lead" })).toBeInTheDocument();
    expect(screen.queryByText("Lead created")).not.toBeInTheDocument();
  });
});
